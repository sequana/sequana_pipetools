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


class OnSuccess:
    def __init__(self, toclean=["fastq_sampling", "logs", "common_logs", "images", "rulegraph"]):
        print("Deprecated. Use OnSuccessCleaner instead")
        self.makefile_filename = "Makefile"
        self.cleanup_filename = "sequana_cleanup.py"
        self.toclean = toclean

    def __call__(self):
        self.add_makefile()
        self.create_recursive_cleanup(self.toclean)

    def add_makefile(self, sections=["bundle", "clean"]):
        makefile = Makefile(sections=sections)
        makefile.makefile_filename = self.makefile_filename
        makefile.save()

    def create_recursive_cleanup(self, additional_dir=[".snakemake"]):
        """Create general cleanup

        :param additional_dir: extra directories to remove

        """
        with open(self.cleanup_filename, "w") as fh:
            fh.write(
                """
import subprocess, glob, os
from easydev import shellcmd

for this in glob.glob("*"):
    if os.path.isdir(this):
        print(" --- Cleaning up %s directory" % this)
        if os.path.exists(this + os.sep + "sequana_cleanup.py"):
            pid = subprocess.Popen(["python", "sequana_cleanup.py"], cwd=this)
            pid.wait()  # we do not want to run e.g. 48 cleanup at the same time

# Remove some files
for this in ["README", "requirements.txt", 'runme.sh', 'config.yaml', 'stats.txt',
             "dag.svg", "rulegraph.svg", "*rules", "*.fa"]:
    try:
        shellcmd("rm %s" % this)
    except:
        print("%s not found (not deleted)" % this)

# Remove some directories
for this in {1}:
    try:
        shellcmd("rm -rf %s" % this)
    except:
        print("%s not found (not deleted)" % this)

shellcmd("rm -rf tmp/")
shellcmd("rm -f {0}")
print("done")
    """.format(
                    self.cleanup_filename, additional_dir
                )
            )


class OnSuccessCleaner:
    """Used in various sequana pipelines to cleanup final results"""

    def __init__(self, pipeline_name=None, bundle=False):
        self.makefile_filename = "Makefile"
        self.files_to_remove = [
            "config.yaml",
            "multiqc_config.yaml",
            "cluster_config.json",
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

    def add_bundle(self, input="*", output="bundle.tar.gz"):
        self.bundle = True
        self.bundle_input = input
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
    pipelines = [m for m in modules if Module(m).is_pipeline()]
    rules = [rule for rule in modules if not Module(rule).is_pipeline()]

    import numpy as np
    import pandas as pd

    L, C = len(rules), len(pipelines)
    df = pd.DataFrame(np.zeros((L, C)), dtype=int, index=rules, columns=pipelines)

    for pipeline in pipelines:
        snakefile = Module(pipeline).snakefile
        with open(snakefile) as fh:
            data = fh.readlines()
            data = [x for x in data if x.strip().startswith("include:")]
            for line in data:
                for rule in rules:
                    if '"' + rule + '"' in line or "'" + rule + "'" in line or rule + "(" in line:
                        df.loc[rule, pipeline] += 1
    return df


def message(mes):
    """Dedicated print function to include in Snakefiles

    In a Snakefile, the stand print function may interfer with other process
    An example is the creation of the dag file. Not sure this is a bug but
    meanwhile, one must use this function to print information.

    This adds the // -- characters in front of the prin statements."""
    logger.info("// -- " + mes)


def build_dynamic_rule(code, directory):
    """Create a rule in a unique file in .snakameke/sequana

    The filenames must be unique, and stored in .snakemake to not
    pollute /tmp

    """
    import uuid

    # Create directory if it does not exist
    from easydev import mkdirs

    mkdirs(directory + ".snakemake/sequana")
    # a unique identifier
    filename = directory
    filename += os.sep.join([".snakemake", "sequana", str(uuid.uuid4())])
    filename += ".rules"
    # Create the file and return its name so that it can be used inside a
    # pipeline
    fh = open(filename, "w")
    fh.write(code)
    fh.close()
    return filename


def create_cleanup(targetdir, exclude=["logs"]):
    """A script to include in directory created by the different pipelines to
    cleanup the directory"""
    filename = targetdir + os.sep + "sequana_cleanup.py"
    with open(filename, "w") as fout:
        fout.write(
            """
import glob, os, shutil, time
from easydev import shellcmd

exclude = {}
for this in glob.glob("*"):
    if os.path.isdir(this) and this not in exclude and this.startswith('report') is False:
        print('Deleting %s' % this)
        time.sleep(0.1)
        shellcmd("rm -rf %s" % this)
shellcmd("rm -f  snakejob.* slurm-*")
shellcmd("rm -rf .snakemake")
shellcmd("rm -f sequana_cleanup.py")
""".format(
                exclude
            )
        )
    return filename
