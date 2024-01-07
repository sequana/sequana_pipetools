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
from pathlib import Path

from sequana_pipetools import logger

from .slurm import SlurmParsing


class PipeError:
    """A factory to deal with errors"""

    def __init__(self, *args, **kwargs):
        pass

    def status(self, working_directory="./", logs_directory="logs"):
        try:  # let us try to introspect the slurm files
            dj = SlurmParsing(working_directory, logs_directory)
            print(dj)
        except Exception as err:  # pragma: no cover
            print(err)
