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

from sequana_pipetools.snaketools.slurm import SlurmParsing


class PipeError:
    """A factory to deal with errors"""

    def __init__(self, *args, **kwargs):
        pass

    def status(self, working_directory="./", logs_directory="logs"):

        print("\n\u274C one or several errors were detected. Please check carefully the above message, or the logs/ directory (for HPC/cluster usage). In the later case, some hints may be provided here below. " )

        # we allows slurm to be detected even though we are not on a cluster
        # this allows users to debug slurm job through NFS mounting
        try:  # let us try to introspect the slurm files
            dj = SlurmParsing(working_directory, logs_directory)
            print(dj)
        except Exception as err:  # pragma: no cover
            print(err)
