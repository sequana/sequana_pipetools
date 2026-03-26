#
#  This file is part of Sequana software
#
#  Copyright (c) 2016-2021 - Sequana Dev Team (https://sequana.readthedocs.io)
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  Website:       https://github.com/sequana/sequana
#  Documentation: http://sequana.readthedocs.io
#  Contributors:  https://github.com/sequana/sequana/graphs/contributors
##############################################################################
import importlib
import os
import re
import subprocess
import sys
import tempfile

import rich_click as click
from packaging.version import Version

from sequana_pipetools import version
from sequana_pipetools.misc import url2hash
from sequana_pipetools.snaketools.dot_parser import DOTParser
from sequana_pipetools.snaketools.errors import PipeError
from sequana_pipetools.snaketools.pipeline_utils import get_pipeline_statistics
from sequana_pipetools.snaketools.sequana_config import SequanaConfig

if Version(click.__version__) >= Version("1.9.0"):
    click.rich_click.TEXT_MARKUP = "markdown"
    click.rich_click.OPTIONS_TABLE_COLUMN_TYPES = ["required", "opt_short", "opt_long", "help"]
    click.rich_click.OPTIONS_TABLE_HELP_SECTIONS = ["help", "deprecated", "envvar", "default", "required", "metavar"]
else:
    click.rich_click.USE_MARKDOWN = True
    click.rich_click.SHOW_METAVARS_COLUMN = False
    click.rich_click.APPEND_METAVARS_HELP = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.FOOTER_TEXT = (
    "Authors: Thomas Cokelaer, Dimitri Desvillechabrol -- http://github.com/sequana/sequana_pipetools"
)
click.rich_click.OPTION_GROUPS["sequana_pipetools"] = [
    {
        "name": "Diagnostics",
        "options": ["--diagnose", "--slurm-diag", "--workdir", "--provider", "--model"],
    },
    {
        "name": "Pipeline Builder",
        "options": ["--init-new-pipeline", "--config-to-schema"],
    },
    {
        "name": "Completion",
        "options": ["--completion", "--overwrite"],
    },
]
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


class ClickComplete:
    # For the -o default, this was an issue with compgen removing the slashes on
    # directrories . Solution was found here:
    # https://stackoverflow.com/questions/12933362/getting-compgen-to-include-slashes-on-directories-when-looking-for-files
    # Before using this option, a second directory could not be completed e.g.
    # in --databases, only the first argument could be completed, which was
    # really annoying.

    # KEEP '#version:' on first line since it is used in
    # sequana/pipeline_common.py right now
    setup = """#version: {version}
#info:
function _mycomplete_{pipeline_name}()
{{
    local cur prev opts
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    opts="{options}"
    case "${{prev}}" in
    """

    teardown = """
        #;;
    esac
    #if [[ ${{cur}} == -* ]] ; then
        COMPREPLY=( $(compgen -W "${{opts}}" -- ${{cur}}) )
        return 0
    #fi

}}
#complete -d -X '.[^./]*' -F _mycomplete_ sequana_{pipeline_name}
complete -o nospace -o default -F _mycomplete_{pipeline_name} sequana_{pipeline_name}
    """

    def __init__(self, pipeline_name):
        self._set_pipeline_name(pipeline_name)

    def _get_pipeline_name(self):
        return self._pipeline_name

    def _set_pipeline_name(self, name):
        self._pipeline_name = name
        self._init_config_file()
        self._init_version()

    pipeline_name = property(_get_pipeline_name, _set_pipeline_name)

    def save_fish_completion(self):
        out = []
        for action in self._actions:
            # Prefer long options (--foo); fall back to short (-f)
            long_opts = [o for o in action.opts if o.startswith("--")]
            short_opts = [o for o in action.opts if o.startswith("-") and not o.startswith("--")]
            if long_opts:
                flag = f"-l {long_opts[0][2:]}"
            elif short_opts:
                flag = f"-s {short_opts[0][1:]}"
            else:
                continue  # skip options with no recognisable flag

            type_name = action.type.name if action.type is not None else "string"
            if type_name == "choice":
                choices = " ".join(action.type.choices)
                out.append(f"complete -c sequana_{self.pipeline_name} {flag} -f -a '{choices}'")
            elif type_name == "path":
                out.append(f"complete -c sequana_{self.pipeline_name} {flag} -r -a '(ls -d */)'")
            else:
                out.append(f"complete -c sequana_{self.pipeline_name} {flag}")

        with open(f"{self.config_path}/{self.pipeline_name}.fish", "w") as f:
            f.write("\n".join(out))

    def save_completion_script(self):
        config_path = self.config_path
        pipeline_name = self.pipeline_name

        output_filename = f"{config_path}/{pipeline_name}.sh"

        arguments = self.get_arguments()

        with open(output_filename, "w") as fout:
            fout.write(
                self.setup.format(
                    version=self.pipeline_version, pipeline_name=pipeline_name, options=" ".join(arguments)
                )
            )
            for action in self._actions:
                name = action.opts[0]

                if action.type.name == "choice":
                    fout.write(self.set_option_with_choice(name, action.type.choices))
                elif action.type.name == "path":
                    fout.write(self.set_option_path(name))
                # elif action.type.name"-file"):
                #    fout.write(self.set_option_file(action.name))
                # elif action.name in ["--databases", "--from-project"]:
                #    fout.write(self.set_option_directory(action.name))
            fout.write(self.teardown.format(pipeline_name=self.pipeline_name))

    def _init_config_file(self):
        # do not import sequana, save time, let us use easydev
        from easydev import CustomConfig

        configuration = CustomConfig("sequana", verbose=False)
        sequana_config_path = configuration.user_config_dir
        path = sequana_config_path + os.sep + "pipelines"
        if os.path.exists(path):
            pass
        else:  # pragma: no cover
            os.mkdir(path)
        self.config_path = path
        return path

    def _init_version(self):
        importlib.import_module("sequana_pipelines.{}".format(self.pipeline_name))
        importlib.import_module("sequana_pipelines.{}.main".format(self.pipeline_name))
        module = sys.modules["sequana_pipelines.{}".format(self.pipeline_name)]
        version = module.version
        self.pipeline_version = version

    def get_arguments(self):
        importlib.import_module("sequana_pipelines.{}".format(self.pipeline_name))
        importlib.import_module("sequana_pipelines.{}.main".format(self.pipeline_name))
        module = sys.modules["sequana_pipelines.{}".format(self.pipeline_name)]

        main = module.__getattribute__("main")
        self._actions = [x for x in main.main.params]
        arguments = [f"{x.opts[0]}" for x in main.main.params]
        arguments = [x.replace("_", "-") for x in arguments]
        arguments = sorted(arguments)

        return arguments

    def set_option_with_choice(self, option_name, option_choices):

        option_choices = " ".join(option_choices)
        data = f"""
            {option_name})
                local choices="{option_choices}"
                COMPREPLY=( $(compgen -W "${{choices}}" -- ${{cur}}) )
                return 0
                ;;"""
        return data

    def set_option_path(self, option_name):
        data = f"""
            {option_name})
                xpat=".[!.]*"
                COMPREPLY=( $(compgen -X "${{xpat}}" -d ${{cur}}) )
                return 0
                ;;"""
        return data

    def set_option_file(self, option_name):
        data = f"""
            {option_name})
                COMPREPLY=( $(compgen  -f ${{cur}}) )
                return 0
                ;;"""
        return data


_PLAIN_EXPLANATION_RE = re.compile(
    r"(?:#{1,3}\s*|^\*\*)?Plain\s+Explanation[:\*#\s]*\*?\*?\s*\n(.*?)(?=\n#{1,3}\s|\n\*\*[A-Z]|\Z)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)


def _print_diagnosis(result: str) -> None:
    """Print the LLM diagnosis, pulling the Plain Explanation into a Rich panel."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(
        Panel(
            "[bold]These are generic AI-generated tips and may not accurately reflect your specific situation.[/bold]\n"
            "Always verify the suggested fixes before applying them.",
            title="⚠️  AI Disclaimer",
            border_style="bold yellow",
            padding=(1, 2),
        )
    )
    # Split off the Sequana tips block (appended after "---")
    tips_text = ""
    if "\n---\n" in result:
        llm_part, tips_part = result.split("\n---\n", 1)
        tips_text = tips_part.strip()
    else:
        llm_part = result

    m = _PLAIN_EXPLANATION_RE.search(llm_part)
    if m:
        plain_text = m.group(1).strip()
        console.print(Panel(plain_text, title="💡 Plain Explanation", border_style="bold cyan", padding=(1, 2)))
        # print the rest without the Plain Explanation section
        rest = llm_part[: m.start()] + llm_part[m.end() :]
        if rest.strip():
            click.echo(rest.strip())
    else:
        click.echo(llm_part.strip())

    if tips_text:
        console.print(Panel(tips_text, title="💡 Sequana tips", border_style="bold green", padding=(1, 2)))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--version", is_flag=True)
@click.option(
    "--dot2png", type=click.STRING, help="convert the input.dot into PNG file. Output name is called INPUT.sequana.png"
)
@click.option(
    "--completion",
    type=click.STRING,
    help="""Name of a pipelines for which you wish to create the completion file. Set to a valid Sequana pipeline name that must be installed""",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="""Overwrite files in sequana config pipeline directory (used with
--completion)""",
)
@click.option("--stats", is_flag=True, help="""Plot some stats related to the Sequana pipelines (installed)""")
@click.option(
    "--config-to-schema",
    type=click.Path(file_okay=True, dir_okay=False),
    help="""Given a config file, this command creates a draft schema file""",
)
@click.option("--slurm-diag", is_flag=True, help="Scans slurm files and get summary information")
@click.option("--url2hash", type=click.STRING, help="For developers. Convert a URL to hash mame. ")
@click.option(
    "--init-new-pipeline",
    is_flag=True,
    help="Give name of new pipeline and this will create full structure for a new sequana pipeline",
)
@click.option(
    "--diagnose",
    is_flag=True,
    help="Diagnose pipeline errors using an LLM (see --provider). Run from the pipeline working directory.",
)
@click.option(
    "--workdir",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Pipeline working directory for --diagnose.",
)
@click.option(
    "--provider",
    default="mistral",
    show_default=True,
    type=click.Choice(["mistral", "openai"], case_sensitive=False),
    help="LLM provider for --diagnose. 'mistral' has a free tier (MISTRAL_API_KEY); 'openai' requires a paid account (OPENAI_API_KEY).",
)
@click.option(
    "--model",
    default=None,
    help="Model name for --diagnose. Defaults to mistral-small-latest (mistral) or gpt-4o-mini (openai).",
)
def main(**kwargs):
    """Pipetools utilities for the Sequana project (sequana.readthedocs.io)

    The pipetools package is dedicated to the developers of Sequana pipelines.
    However, Pipetools provides a set of utilities starting with the completion
    script for the different pipeline.

    To create a completion script, first install the pipeline::

        pip install sequana_multitax

    Then, type (--force to replace existing one):

        sequana_pipetools --completion multitax --force

    """

    if not any(kwargs.values()):
        click.echo(click.get_current_context().get_help())
        return

    if kwargs["version"]:
        click.echo(f"sequana_pipetools v{version}")
        return
    elif kwargs["url2hash"]:
        click.echo(url2hash(kwargs["url2hash"]))
    elif kwargs["dot2png"]:
        name = kwargs["dot2png"]
        if not name.endswith(".dot"):
            raise ValueError(f"Input file must have a .dot extension, got: {name}")
        outname = name.replace(".dot", ".sequana.png")
        with tempfile.NamedTemporaryFile(mode="w") as fout:
            d = DOTParser(name)
            d.add_urls(fout.name)
            cmd = f"dot -Tpng {fout.name} -o {outname}"
            subprocess.call(cmd.split())

    elif kwargs["completion"]:
        name = kwargs["completion"]

        if kwargs["overwrite"] is True:
            choice = "y"
        else:  # pragma: no cover
            msg = f"This action will replace the {name}.sh and {name}.fish files stored in ~/.config/sequana/pipelines. Do you want to proceed y/n: "
            choice = input(msg)
        if choice != "y":  # pragma: no cover
            sys.exit(0)

        try:
            c = ClickComplete(name)
            c.save_completion_script()
            c.save_fish_completion()
        except Exception:  # pragma: no cover
            click.echo(f"# Warning {name} could not be imported. Nothing done")
        finally:
            click.echo("Please follow those instructions: \n")
            click.echo(f"Bash:\n\tsource ~/.config/sequana/pipelines/{name}.sh")
            click.echo("        #Add the line above in your .bashrc environment if needed\n")
            click.echo(f"Fish:\n\tsource ~/.config/sequana/pipelines/{name}.fish")
            click.echo("        #Add the line above in your .fishrc environment if needed\n")
    elif kwargs["stats"]:
        wrappers, rules = get_pipeline_statistics()
        click.echo("\n ==== Number of wrappers per pipeline")
        click.echo(wrappers.sum(axis=0))
        click.echo("\n ==== Number of time a wrapper is used")
        click.echo(wrappers.sum(axis=1))
        click.echo("\n ==== Number of rules used")
        click.echo(rules)
    elif kwargs["config_to_schema"]:
        config_file = kwargs["config_to_schema"]
        cfg = SequanaConfig(config_file)
        cfg.create_draft_schema()
    elif kwargs["slurm_diag"]:
        click.echo("Looking for slurm files")
        p = PipeError()
        p.status(".")
    elif kwargs["init_new_pipeline"]:  # pragma: no cover
        cmd = "cookiecutter https://github.com/sequana/sequana_pipeline_template -o . --overwrite-if-exists"
        subprocess.run(cmd.split(), capture_output=False)
    elif kwargs["diagnose"]:
        from sequana_pipetools.diagnose import diagnose

        workdir = kwargs["workdir"]
        provider = kwargs["provider"]
        model = kwargs["model"]  # may be None → uses provider default
        click.echo(f"Collecting pipeline logs from: {workdir}  [provider: {provider}]\n")
        try:
            result = diagnose(workdir=workdir, provider=provider, model=model)
            _print_diagnosis(result)
        except (ImportError, EnvironmentError, ValueError) as exc:
            click.echo(f"[ERROR] {exc}", err=True)
            sys.exit(1)


if __name__ == "__main__":
    main()  # pragma: no cover
