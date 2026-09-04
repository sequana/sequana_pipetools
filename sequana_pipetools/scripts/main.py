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
import html
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import rich_click as click
from packaging.version import Version

from sequana_pipetools import version
from sequana_pipetools.misc import url2hash
from sequana_pipetools.monitor import run_monitor
from sequana_pipetools.snaketools.dot_parser import DOTParser
from sequana_pipetools.snaketools.errors import PipeError
from sequana_pipetools.snaketools.pipeline_utils import get_pipeline_statistics
from sequana_pipetools.snaketools.profile import create_profile
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
    {
        "name": "Rule graph",
        "options": ["--dot2png", "--output"],
    },
    {
        "name": "External wrapper",
        "options": [
            "--wrapper",
            "--wrapper-name",
            "--wrapper-profile",
            "--wrapper-jobs",
            "--wrapper-keep-going",
            "--wrapper-slurm-memory",
            "--wrapper-slurm-queue",
            "--workdir",
        ],
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


def _convert_dot_to_png(name: str, output: Optional[str] = None, content: Optional[str] = None) -> str:
    if content is not None:
        if not content.strip():
            raise ValueError("No data found on the standard input.")
        d = DOTParser(content=content)
        outname = output or "rulegraph.sequana.png"
    else:
        if not name.endswith(".dot"):
            raise ValueError(f"Input file must have a .dot extension, got: {name}")
        d = DOTParser(name)
        outname = output or name.replace(".dot", ".sequana.png")

    with tempfile.NamedTemporaryFile(mode="w") as fout:
        d.add_urls(fout.name)
        try:
            status = subprocess.call(["dot", "-Tpng", fout.name, "-o", outname])
        except FileNotFoundError:
            raise click.ClickException("The 'dot' executable was not found. Please install graphviz.")
    if status != 0:
        raise click.ClickException(f"dot failed to convert your input into {outname} (error {status})")
    return outname


def _format_elapsed(seconds: float) -> str:
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes:d}m {seconds:02d}s"
    return f"{seconds:d}s"


def _get_snakemake_version() -> str:
    try:
        import snakemake

        return snakemake.__version__
    except Exception:
        return "unknown"


def _create_wrapper_rulegraph(snakefile: str, profile: str, workdir: Path) -> Path:
    dotfile = workdir / ".sequana" / "rulegraph.dot"
    pngfile = workdir / ".sequana" / "rulegraph.sequana.png"
    cmd = ["snakemake", "-s", snakefile, "--profile", profile, "--rulegraph"]
    result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or f"snakemake exited with status {result.returncode}"
        raise click.ClickException(f"Could not generate rulegraph: {msg}")
    if not result.stdout.strip():
        raise click.ClickException("Could not generate rulegraph: snakemake returned an empty graph.")
    dotfile.write_text(result.stdout)
    _convert_dot_to_png(str(dotfile), output=str(pngfile))
    return pngfile


def _write_wrapper_summary(
    workdir: Path,
    snakefile: Path,
    profile: str,
    pipeline_name: str,
    start_dt: datetime,
    end_dt: datetime,
    returncode: int,
    rulegraph_png: Optional[Path],
) -> Path:
    summary = workdir / "summary.html"
    snakelog = workdir / ".sequana" / "snakemake.log"
    profile_config = workdir / profile / "config.yaml"
    status = "success" if returncode == 0 else "failure"
    escaped_name = html.escape(pipeline_name)
    rows = [
        ("Status", status),
        ("Exit code", str(returncode)),
        ("Snakefile", str(snakefile)),
        ("Working directory", str(workdir)),
        ("Profile", profile),
        ("Profile config", str(profile_config.resolve()) if profile_config.exists() else "not created"),
        ("Started", start_dt.isoformat()),
        ("Finished", end_dt.isoformat()),
        ("Elapsed", _format_elapsed((end_dt - start_dt).total_seconds())),
        ("Host", platform.node() or "unknown"),
        ("Platform", platform.platform()),
        ("Python", sys.version.split()[0]),
        ("Snakemake", _get_snakemake_version()),
        ("Executable", sys.executable),
    ]

    links = []
    if rulegraph_png and rulegraph_png.exists():
        links.append(
            f'<li><a href="{html.escape(os.path.relpath(rulegraph_png, workdir))}">Rulegraph PNG</a></li>'
        )
    if snakelog.exists():
        links.append(f'<li><a href="{html.escape(os.path.relpath(snakelog, workdir))}">Snakemake log</a></li>')
    if profile_config.exists():
        links.append(
            f'<li><a href="{html.escape(os.path.relpath(profile_config, workdir))}">Profile config</a></li>'
        )

    lines = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>{escaped_name} summary</title>",
        "<style>body{font-family:sans-serif;margin:2rem;line-height:1.5}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccc;padding:.4rem .6rem;text-align:left}th{background:#f5f5f5}</style>",
        "</head><body>",
        f"<h1>{escaped_name} summary</h1>",
        "<table>",
        "<tr><th>Field</th><th>Value</th></tr>",
    ]
    for key, value in rows:
        lines.append(f"<tr><td>{html.escape(key)}</td><td>{html.escape(value)}</td></tr>")
    lines.extend(["</table>"])
    if links:
        lines.append("<h2>Artifacts</h2><ul>")
        lines.extend(links)
        lines.append("</ul>")
    lines.append("</body></html>")
    summary.write_text("\n".join(lines))
    return summary


def _run_wrapper(
    snakefile: str,
    workdir: str,
    wrapper_name: str,
    wrapper_profile: str,
    wrapper_jobs: int,
    wrapper_keep_going: bool,
    wrapper_slurm_memory: str,
    wrapper_slurm_queue: str,
) -> int:
    workdir_path = Path(workdir).resolve()
    workdir_path.mkdir(parents=True, exist_ok=True)
    snakefile_path = Path(snakefile).resolve()

    profile_kwargs = {
        "jobs": wrapper_jobs,
        "wrappers": os.environ.get("SEQUANA_WRAPPERS", "https://raw.githubusercontent.com/sequana/sequana-wrappers/"),
        "forceall": False,
        "keep_going": wrapper_keep_going,
        "use_apptainer": False,
        "apptainer_prefix": "",
        "apptainer_args": "",
    }
    if wrapper_profile == "slurm":
        profile_kwargs.update(
            {
                "partition": wrapper_slurm_queue,
                "qos": wrapper_slurm_queue,
                "memory": wrapper_slurm_memory,
            }
        )

    profile_dir = create_profile(workdir_path, wrapper_profile, **profile_kwargs)

    rulegraph_png = None
    try:
        rulegraph_png = _create_wrapper_rulegraph(str(snakefile_path), profile_dir, workdir_path)
        click.echo(f"Created {rulegraph_png}")
    except Exception as exc:
        click.echo(f"# Warning: {exc}", err=True)

    start_dt = datetime.now().astimezone()
    returncode = run_monitor(str(snakefile_path), profile_dir, wrapper_name, "", str(workdir_path))
    end_dt = datetime.now().astimezone()
    summary = _write_wrapper_summary(
        workdir_path, snakefile_path, profile_dir, wrapper_name, start_dt, end_dt, returncode, rulegraph_png
    )
    click.echo(f"Created {summary}")
    return returncode


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--version", is_flag=True)
@click.option(
    "--dot2png",
    type=click.STRING,
    help="""convert the input.dot into PNG file. Output name is called INPUT.sequana.png.
Use - to read the dot file from the standard input e.g. *snakemake --rulegraph | sequana_pipetools --dot2png -*
in which case the output is called rulegraph.sequana.png unless --output is used.""",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, dir_okay=False),
    default=None,
    help="Name of the PNG file created by --dot2png.",
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
@click.option("--url2hash", type=click.STRING, help="For developers. Convert a URL into its hash name.")
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
    help="Pipeline working directory for --diagnose and --wrapper.",
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
@click.option(
    "--wrapper",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Run an arbitrary Snakefile with a generated profile, rulegraph PNG and summary report.",
)
@click.option("--wrapper-name", default="External Snakemake", show_default=True, help="Display name used in reports.")
@click.option(
    "--wrapper-profile",
    default="local",
    show_default=True,
    type=click.Choice(["local", "slurm"]),
    help="Execution profile for --wrapper.",
)
@click.option("--wrapper-jobs", default=4, show_default=True, type=int, help="Number of jobs for the wrapper profile.")
@click.option(
    "--wrapper-keep-going",
    is_flag=True,
    help="Continue running independent jobs after a failure when using --wrapper.",
)
@click.option(
    "--wrapper-slurm-memory",
    default="4G",
    show_default=True,
    help="Memory requested per SLURM job when using --wrapper-profile slurm.",
)
@click.option(
    "--wrapper-slurm-queue",
    default="common",
    show_default=True,
    help="SLURM partition/queue used with --wrapper-profile slurm.",
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

    if kwargs["output"] and not kwargs["dot2png"]:
        raise click.UsageError("--output is only used together with --dot2png")

    if kwargs["version"]:
        click.echo(f"sequana_pipetools v{version}")
        return
    elif kwargs["url2hash"]:
        click.echo(url2hash(kwargs["url2hash"]))
    elif kwargs["dot2png"]:
        name = kwargs["dot2png"]
        if name == "-":
            # e.g. snakemake --rulegraph | sequana_pipetools --dot2png -
            content = sys.stdin.read()
            if not content.strip():
                raise ValueError("No data found on the standard input.")
            d = DOTParser(content=content)
            outname = kwargs["output"] or "rulegraph.sequana.png"
        else:
            if not name.endswith(".dot"):
                raise ValueError(f"Input file must have a .dot extension, got: {name}")
            d = DOTParser(name)
            outname = kwargs["output"] or name.replace(".dot", ".sequana.png")

        with tempfile.NamedTemporaryFile(mode="w") as fout:
            d.add_urls(fout.name)
            try:
                status = subprocess.call(["dot", "-Tpng", fout.name, "-o", outname])
            except FileNotFoundError:
                raise click.ClickException("The 'dot' executable was not found. Please install graphviz.")
        if status != 0:
            raise click.ClickException(f"dot failed to convert your input into {outname} (error {status})")
        click.echo(f"Created {outname}")

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
    elif kwargs["wrapper"]:
        sys.exit(
            _run_wrapper(
                kwargs["wrapper"],
                kwargs["workdir"],
                kwargs["wrapper_name"],
                kwargs["wrapper_profile"],
                kwargs["wrapper_jobs"],
                kwargs["wrapper_keep_going"],
                kwargs["wrapper_slurm_memory"],
                kwargs["wrapper_slurm_queue"],
            )
        )


if __name__ == "__main__":
    main()  # pragma: no cover
