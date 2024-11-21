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
import subprocess
import sys
import tempfile

import rich_click as click

from sequana_pipetools import version
from sequana_pipetools.misc import url2hash
from sequana_pipetools.snaketools.dot_parser import DOTParser
from sequana_pipetools.snaketools.errors import PipeError
from sequana_pipetools.snaketools.pipeline_utils import get_pipeline_statistics
from sequana_pipetools.snaketools.sequana_config import SequanaConfig

click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_METAVARS_COLUMN = False
click.rich_click.APPEND_METAVARS_HELP = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.FOOTER_TEXT = (
    "Authors: Thomas Cokelaer, Dimitri Desvillechabrol -- http://github.com/sequana/sequana_pipetools"
)
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
    "--force",
    is_flag=True,
    help="""overwrite files in sequana config pipeline directory (used with
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

    if kwargs["version"]:
        click.echo(f"sequana_pipetools v{version}")
        return
    elif kwargs["url2hash"]:
        click.echo(url2hash(kwargs["url2hash"]))
    elif kwargs["dot2png"]:
        name = kwargs["dot2png"]
        assert name.endswith(".dot")
        outname = name.replace(".dot", ".sequana.png")
        with tempfile.NamedTemporaryFile(mode="w") as fout:
            d = DOTParser(name)
            d.add_urls(fout.name)
            cmd = f"dot -Tpng {fout.name} -o {outname}"
            subprocess.call(cmd.split())

    elif kwargs["completion"]:
        name = kwargs["completion"]

        if kwargs["force"] is True:
            choice = "y"
        else:  # pragma: no cover
            msg = f"This action will replace the {name}.sh file stored in ~/.config/sequana/pipelines. Do you want to proceed y/n: "
            choice = input(msg)
        if choice != "y":  # pragma: no cover
            sys.exit(0)

        try:
            c = ClickComplete(name)
            c.save_completion_script()
        except Exception:  # pragma: no cover
            click.echo(f"# Warning {name} could not be imported. Nothing done")
        finally:
            click.echo("Please source the files using:: \n")
            click.echo("    source ~/.config/sequana/pipelines/{}.sh".format(name))
            click.echo("\nto activate the completion. Add the line above in your environement")
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


if __name__ == "__main__":
    main()  # pragma: no cover
