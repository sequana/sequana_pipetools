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
import glob

from .slurm import DebugJob


class PipeError:
    def __init__(self, name, **kwars):
        self.name = name

    def status(self, slurm_directory="./"):
        print(
            f"An error occurred during the execution. Please fix the issue and run the script again (sh {self.name}.sh)"
        )

        filenames = glob.glob(slurm_directory + "slurm*")
        if len(filenames):  # pragma: no cover
            dj = DebugJob(slurm_directory)
            print(dj)
