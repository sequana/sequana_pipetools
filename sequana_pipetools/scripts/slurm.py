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
import rich_click as click
from sequana_pipetools.slurm import DebugJob

click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_METAVARS_COLUMN = False
click.rich_click.APPEND_METAVARS_HELP = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.SHOW_ARGUMENTS = True

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--directory", "directory", type=click.STRING, default=".", help="Directory where to introspect slurm jobs"
)
@click.option("--context", type=click.INT, default=5, help="""Number of errors to show""")
def main(**kwargs):
    """
    Scans slurm jobs trying to infer useful summary of errors

    ----

    Examples:

        sequana_slurm_status
        sequana_slurm_status --directory ./rnaseq/

    """
    dj = DebugJob(kwargs["directory"], context=kwargs["context"])
    print(dj)


if __name__ == "__main__":
    main()
