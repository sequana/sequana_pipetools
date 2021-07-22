#  This file is part of Sequana software
#
#  Copyright (c) 2016-2021 - Sequana Development Team
#
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
import glob


class PipeError():
    def __init__(self, name, **kwars):
        self.name = name

    def status(self, slurm_directory="./"):
        print(f"An error occurred during the execution. Please fix the issue and run the script again (sh {self.name}.sh)")

        filenames = glob.glob(slurm_directory + "slurm*")
        if len(filenames): #pragma: no cover
            from sequana_pipetools.slurm import DebugJob
            dj = DebugJob(slurm_directory)
            print(dj)


