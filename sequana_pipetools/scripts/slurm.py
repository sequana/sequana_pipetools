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
import argparse
import os
import re
import sys
from pathlib import Path

import colorlog
import parse

from sequana_pipetools.slurm import DebugJob

logger = colorlog.getLogger(__name__)


class Options(argparse.ArgumentParser):
    def __init__(self, prog="sequana_slurm_status"):
        usage = """

    sequana_slurm_status
    sequana_slurm_status --directory ./rnaseq/

    """

        super(Options, self).__init__(
            usage=usage,
            prog=prog,
            description="""This tool scan slurm jobs trying to infer useful summary of errors""",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

        self.add_argument(
            "--directory",
            type=str,
            default=".",
            help="""Directory where to introspect slurm jobs""",
        )
        self.add_argument("--context", type=int, default=5, help="""Number of errors to show""")


def main(args=None):

    if args is None:
        args = sys.argv[:]

    user_options = Options()

    if "--help" in args:
        user_options.parse_args(["prog", "--help"])
    else:
        options = user_options.parse_args(args[1:])

    dj = DebugJob(options.directory, context=options.context)
    print(dj)


if __name__ == "__main__":
    main()
