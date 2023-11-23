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
import os

import colorlog
import easydev

from .module import Module, modules

logger = colorlog.getLogger(__name__)


class Makefile:
    def __init__(self, sections=["bundle"]):
        self.makefile_filename = "Makefile"
        self.cleanup_filename = "sequana_cleanup.py"
        self.text = ""
        for section in sections:
            try:
                getattr(self, f"add_{section}")()
            except AttributeError:
                logger.warning(f"no {section} section found in Makefile class")

    def add_remove_done(self):
        self.text += "\nremove_done:\n\trm -f ./*/*/*.done"

    def add_clean(self):
        txt = "clean:\n"
        th = self.cleanup_filename
        txt += '\tif [ -f %s ]; then python %s ; else echo "cleaned already"; fi;\n' % (th, th)
        self.text += txt

    def add_bundle(self):
        txt = "bundle:\n"
        if easydev.cmd_exists("pigz"):
            txt += "\ttar cvf - * | pigz  -p 4 > results.tar.gz\n"
        else:
            txt += "\ttar cvfz results.tar.gz *\n"
        self.text += txt

    def save(self):
        with open(self.makefile_filename, "w") as fh:
            fh.write(self.text)


class OnSuccessCleaner:
    """Used in various sequana pipelines to cleanup final results"""

    def __init__(self, pipeline_name=None, bundle=False, outdir="."):
        self.makefile_filename = f"{outdir}/Makefile"
        self.files_to_remove = [
            "config.yaml",
            "multiqc_config.yaml",
            "slurm*out",
            "stats.txt",
            "unlock.sh",
            "schema.yaml",
        ]
        if pipeline_name:
            self.files_to_remove.append("{}.sh".format(pipeline_name))
            self.files_to_remove.append("{}.rules".format(pipeline_name))
        self.directories_to_remove = [".snakemake"]
        self.bundle = bundle
        self.custom_commands = ""

    def add_bundle(self, input_pattern="*", output="bundle.tar.gz"):
        self.bundle = True
        self.bundle_input = input_pattern
        self.bundle_output = output

    def add_makefile(self):
        makefile = 'all:\n\techo "type *make clean* to delete temporary files"\n'
        if self.bundle:
            makefile += "bundle:\n\ttar cvfz {} {}\n".format(self.bundle_output, self.bundle_input)
        makefile += "clean: clean_files clean_directories custom\n"

        files = self.files_to_remove + [self.makefile_filename]
        # in case commas are added in the config file
        files = [x.replace(",", "") for x in files]

        makefile += "clean_files:\n\trm -f {}\n".format(" ".join(files))

        dirs = self.directories_to_remove
        makefile += "clean_directories:\n\trm -rf {}\n".format(" ".join(dirs))

        # custom commands
        makefile += "custom:\n\t{}\n".format(self.custom_commands)

        with open(self.makefile_filename, "w") as fh:
            fh.write(makefile)

        logger.info("Once done, please clean up the directory using: 'make clean'")


def get_pipeline_statistics():
    """Get basic statistics about the pipelines

    Count rule used per pipeline and returns a dataframe with rules as index
    and pipeline names as columns

    ::

        from sequana.snaketools import get_pipeline_statistics
        df = get_pipeline_statistics()
        df.sum(axis=1).sort_values(ascending=False)
        df.sum(axis=0).plot(kind="barh")

    """
    pipelines = sorted([m for m in modules if Module(m).is_pipeline()])

    import numpy as np
    import pandas as pd

    def get_wrapper_names(filename):
        wrappers = set()
        with open(snakefile) as fh:
            data = fh.readlines()
            data = [x.strip('\n"').split("/")[-1] for x in data if "/wrappers/" in x]
            wrappers.update(data)
        return wrappers

    # first pass to identify the wrappers
    wrappers = set()
    for pipeline in pipelines:
        snakefile = Module(pipeline).snakefile
        wrappers.update(get_wrapper_names(snakefile))

    # second pass to populate the matrix
    wrappers = sorted(list(wrappers))
    L, C = len(wrappers), len(pipelines)
    df = pd.DataFrame(np.zeros((L, C)), dtype=int, index=wrappers, columns=pipelines)
    for pipeline in pipelines:
        snakefile = Module(pipeline).snakefile
        wrappers = get_wrapper_names(snakefile)
        for wrapper in wrappers:
            df.loc[wrapper, pipeline] += 1

    df.columns = [x.replace("pipeline:", "") for x in df.columns]
    return df


def message(mes):
    """Dedicated print function to include in Snakefiles

    In a Snakefile, the stand print function may interfer with other process
    An example is the creation of the dag file. Not sure this is a bug but
    meanwhile, one must use this function to print information.

    This adds the // -- characters in front of the prin statements."""
    logger.info("// -- " + mes)

