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
import sys

from easydev import cmd_exists

from .misc import print_version

__all__ = [
    "GeneralOptions",
    "SlurmOptions",
    "SnakemakeOptions",
    "TrimmingOptions",
    "KrakenOptions",
    "InputOptions",
    "FeatureCountsOptions",
]


def init_pipeline(NAME):
    print("init_pipeline is deprecated, please use before_pipeline instead")
    before_pipeline(NAME)


def before_pipeline(NAME):
    """A function to provide --version and --deps for all pipelines"""

    if "--version" in sys.argv:
        print_version(NAME)
        sys.exit(0)

    if "--deps" in sys.argv:
        # Means than sequana must be installed, which we assume if someone uses
        # a pipeline. so must be here and not global import
        from .snaketools import Module

        module = Module("pipeline:" + NAME)
        with open(str(module.requirements), "r") as fin:
            data = fin.read()
        print("Those software will be required for the pipeline to work correctly:\n{}".format(data))
        sys.exit(0)


class GeneralOptions:
    def __init__(self):
        pass

    def add_options(self, parser):
        parser.add_argument(
            "--run-mode",
            dest="run_mode",
            default=None,
            choices=["local", "slurm"],
            help="""run_mode can be either 'local' or 'slurm'. Use local to
                run the pipeline locally, otherwise use 'slurm' to run on a
                cluster with SLURM scheduler. Other clusters are not maintained.
                However, you can set to slurm and change the output shell script
                to fulfill your needs. If unset, sequana searches for the sbatch
                and srun commands. If found, this is set automatically to
                'slurm', otherwise to 'local'.
                """,
        )

        parser.add_argument("--version", action="store_true", help="Print the version and quit")
        parser.add_argument("--deps", action="store_true", help="Show the known dependencies of the pipeline")
        parser.add_argument(
            "--level",
            dest="level",
            default="INFO",
            choices=["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"],
            help="logging level in INFO, DEBUG, WARNING, ERROR, CRITICAL",
        )
        parser.add_argument(
            "--from-project",
            dest="from_project",
            default=None,
            help="""You can initiate a new analysis run from an existing project.
                In theory, sequana project have a hidden .sequana directory,
                which can be used as input. The name of the run directory itself
                should suffice (if .sequana is found inside). From there,
                the config file and the pipeline files are copied in your new
                working directory""",
        )


def guess_scheduler():
    """Guesses whether we are on a SLURM cluster or not.

    If not, we assume a local run is expected.
    """

    if cmd_exists("sbatch") and cmd_exists("srun"):  # pragma: no cover
        return "slurm"
    else:
        return "local"


class SnakemakeOptions:
    def __init__(self, group_name="snakemake", working_directory="analysis"):
        self.group_name = group_name
        self.workdir = working_directory

    def _default_jobs(self):
        if guess_scheduler() == "slurm":  # pragma: no cover
            return 40
        else:
            return 4

    def add_options(self, parser):
        group = parser.add_argument_group(self.group_name)

        group.add_argument(
            "--jobs",
            dest="jobs",
            default=self._default_jobs(),
            help="""Number of jobs to run at the same time (default 4 on a local
                computer, 40 on a SLURM scheduler). This is the --jobs options
                of Snakemake""",
        )
        group.add_argument(
            "--working-directory",
            dest="workdir",
            default=self.workdir,
            help="""where to save the pipeline and its configuration file and
            where the analyse can be run""",
        )
        group.add_argument(
            "--force",
            dest="force",
            action="store_true",
            default=False,
            help="""If the working directory exists, proceed anyway.""",
        )


class InputOptions:
    def __init__(self, group_name="data", input_directory=".", input_pattern="*fastq.gz", add_input_readtag=True):
        """

        By default, single-end data sets. If paired, set is_paired to True
        If so, the add_input_readtag must be set
        """
        self.group_name = group_name
        self.input_directory = input_directory
        self.input_pattern = input_pattern
        self.add_input_readtag = add_input_readtag

    def add_options(self, parser):
        self.group = parser.add_argument_group(self.group_name)
        self.group.add_argument(
            "--input-directory",
            dest="input_directory",
            default=self.input_directory,
            # required=True,
            help="""Where to find the FastQ files""",
        )
        self.group.add_argument(
            "--input-pattern",
            dest="input_pattern",
            default=self.input_pattern,
            help="pattern for the input FastQ files ",
        )

        if self.add_input_readtag:
            self.group.add_argument(
                "--input-readtag",
                dest="input_readtag",
                default="_R[12]_",
                help="""pattern for the paired/single end FastQ. If your files are
                tagged with _R1_ or _R2_, please set this value to '_R[12]_'. If your
                files are tagged with  _1 and _2, you must change this readtag
                accordingly to '_[12]'. This option is used only if
                --paired-data is used""",
            )


class KrakenOptions:
    def __init__(self, group_name="section_kraken"):
        self.group_name = group_name

    def add_options(self, parser):
        group = parser.add_argument_group(self.group_name)

        group.add_argument(
            "--skip-kraken",
            action="store_true",
            default=False,
            help="""If provided, kraken taxonomy is performed. A database must be
                provided (see below). """,
        )

        group.add_argument(
            "--kraken-databases",
            dest="kraken_databases",
            type=str,
            nargs="+",
            default=[],
            help="""Path to a valid set of Kraken database(s).
                If you do not have any, please see https://sequana.readthedocs.io
                or use sequana_taxonomy --download option.
                You may use several, in which case, an iterative taxonomy is
                performed as explained in online sequana documentation""",
        )


class TrimmingOptions:
    description = """
    This section is dedicated to reads trimming and filtering and adapter
    trimming. We currently provide supports for Cutadapt/Atropos and FastP tools.

    This section uniformizes the options for such tools


    """

    def __init__(self, group_name="section_trimming", software=["cutadapt", "atropos", "fastp"]):
        self.group_name = group_name
        self.software = software
        self.software_default = "fastp"

    def add_options(self, parser):

        group = parser.add_argument_group(self.group_name, self.description)

        group.add_argument(
            "--software-choice",
            dest="trimming_software_choice",
            default=self.software_default,
            choices=self.software,
            help="""additional options understood by cutadapt""",
        )

        group.add_argument(
            "--disable-trimming", action="store_true", default=False, help="If provided, disable trimming "
        )

        group.add_argument(
            "--trimming-adapter-read1",
            dest="trimming_adapter_read1",
            default="",
            help="""fastp auto-detects adapters. You may specify the
adapter sequence specificically for fastp or cutadapt/atropos with option for
read1""",
        )

        group.add_argument(
            "--trimming-adapter-read2",
            dest="trimming_adapter_read2",
            default="",
            help="""fastp auto-detects adapters. You may specify the
adapter sequence specificically for fastp or cutadapt/atropos with option for
read1""",
        )

        group.add_argument(
            "--trimming-minimum-length",
            default=20,
            help="""minimum number of bases required; read discarded
otherwise. For cutadapt, default is 20 and for fastp, 15. We use 20 for both by
default.""",
        )

        def quality(x):
            x = int(x)
            if x < 0:
                raise argparse.ArgumentTypeError("quality must be positive")
            return x

        group.add_argument(
            "--trimming-quality",
            dest="trimming_quality",
            default=-1,
            type=quality,
            help="""Trimming quality parameter depends on the algorithm used by
the software behind the scene an may vary greatly; consequently, not provide
a default value. Cutadapt uses 30 by default, fastp uses 15 by default. If
unset, the rnaseq pipeline set the default to 30 for cutadapt and 15 for fastp""",
        )

        # Cutadapt specific
        group.add_argument(
            "--trimming-cutadapt-mode",
            dest="trimming_cutadapt_mode",
            default="b",
            choices=["g", "a", "b"],
            help="""Mode used to remove adapters. g for 5', a for 3', b for both
                5'/3' as defined in cutadapt documentation""",
        )
        group.add_argument(
            "--trimming-cutadapt-options",
            dest="trimming_cutadapt_options",
            default=" -O 6 --trim-n",
            help="""additional options understood by cutadapt. Here, we trim the
Ns; -O 6 is the minimum overlap length between read and adapter for an adapter
to be found""",
        )


class CutadaptOptions:  # pragma: no cover
    description = """
    This section allows you to trim bases (--cutadapt-quality) with poor
    quality and/or remove adapters.

    To remove adapters, you can provide the adapters directly as a 
    string (or a file) using  --cutadapt-fwd (AND --cutadapt-rev" for paired-end data).

    If you set the --cutadapt-adapter-choice to 'none', fwd and reverse
    adapters are set to XXXX (see cutadapt documentation).

    """

    def __init__(self, group_name="section_cutadapt"):
        self.group_name = group_name
        print("CutadaptOptions is deprecated. Will be removed in future versions. Use TrimmingOptions instead")

    def add_options(self, parser):

        group = parser.add_argument_group(self.group_name, self.description)

        group.add_argument(
            "--skip-cutadapt",
            action="store_true",
            default=False,
            help="If provided, fastq cleaning and trimming will be skipped",
        )

        group.add_argument(
            "--cutadapt-fwd",
            dest="cutadapt_fwd",
            default="",
            help="""Provide a adapter as a string of stored in a
                FASTA file. If the file exists, we will store it as expected
                with a preceeding prefix 'file:'""",
        )

        group.add_argument(
            "--cutadapt-rev",
            dest="cutadapt_rev",
            default="",
            help="""Provide a adapter as a string of stored in a
                FASTA file. If the file exists, we will store it as expected
                with a preceeding prefix 'file:'""",
        )

        def quality(x):
            x = int(x)
            if x < 0:
                raise argparse.ArgumentTypeError("quality must be positive")
            return x

        group.add_argument(
            "--cutadapt-quality",
            dest="cutadapt_quality",
            default=30,
            type=quality,
            help="""0  means no trimming, 30 means keep bases with quality
                above 30""",
        )

        group.add_argument(
            "--cutadapt-tool-choice",
            dest="cutadapt_tool_choice",
            default="cutadapt",
            choices=["cutadapt", "atropos"],
            help="Select the prefered tool. Default is cutadapt",
        )

        group.add_argument(
            "--cutadapt-mode",
            dest="cutadapt_mode",
            default="b",
            choices=["g", "a", "b"],
            help="""Mode used to remove adapters. g for 5', a for 3', b for both
                5'/3' as defined in cutadapt documentation""",
        )

        group.add_argument(
            "--cutadapt-options",
            dest="cutadapt_options",
            default=" -O 6 --trim-n",
            help="""additional options understood by cutadapt""",
        )

    def options(self, options):
        """ """
        # do we need to remove adapters at all ?
        if options.cutadapt_adapter_choice == "none":
            options.cutadapt_adapter_choice = None
            options.cutadapt_fwd = "XXXX"
            options.cutadapt_rev = "XXXX"
        # or just the universal ones ?
        elif options.cutadapt_adapter_choice == "universal":
            options.cutadapt_fwd = "GATCGGAAGAGCACACGTCTGAACTCCAGTCACCGATGTATCTCGTATGCCGTCTTCTGC"
            options.cutadapt_rev = "TCTAGCCTTCTCGCAGCACATCCCTTTCTCACATCTAGAGCCACCAGCGGCATAGTAA"
        # or do we have a string or files provided for the fwd/rev ?
        elif options.cutadapt_adapter_choice is None:
            if options.cutadapt_fwd:
                # Could be a string or a file. If a file, check the format
                if os.path.exists(options.cutadapt_fwd):
                    options.cutadapt_fwd = "file:{}".format(os.path.abspath(options.cutadapt_fwd))
            if options.cutadapt_rev:
                # Could be a string or a file. If a file, check the format
                if os.path.exists(options.cutadapt_rev):
                    options.cutadapt_rev = "file:{}".format(os.path.abspath(options.cutadapt_rev))
        elif options.cutadapt_adapter_choice:
            # nothing to do, the cutadapt rules from sequana will use
            # the adapter_choice, and fill the fwd/rev automatically
            pass


class FeatureCountsOptions:
    def __init__(self, group_name="feature_counts", feature_type="gene", attribute="ID", options=None, strandness=None):

        self.group_name = group_name
        self.feature_type = feature_type
        self.attribute = attribute
        self.options = options
        self.strandness = strandness

    def add_options(self, parser):
        group = parser.add_argument_group(self.group_name)
        group.add_argument(
            "--feature-counts-strandness",
            default=self.strandness,
            help="""0 for unstranded, 1 for stranded and 2 for reversely
             stranded. If you do not know, let the pipeline guess for you.""",
        )
        group.add_argument(
            "--feature-counts-attribute",
            default=self.attribute,
            help="""the GFF attribute to use as identifier. If you do not know,
             look at the GFF file or use 'sequana summary YOURFILE.gff' command to get
             information about attributes and  features contained in your annotation file.""",
        )
        group.add_argument(
            "--feature-counts-extra-attributes",
            default=None,
            help="""any extra attribute to add in final feature counts files""",
        )
        group.add_argument(
            "--feature-counts-feature-type",
            default=self.feature_type,
            help="""the GFF feature type (e.g., gene, exon, mRNA, etc). If you
             do not know, look at the GFF file or use 'sequana summary
YOURFILE.gff'. Would you need to perform an analysis on several features, you
can either build your own custom GFF file (see Please see
https://github.com/sequana/rnaseq/wiki) or provide several entries separated by
commas""",
        )
        group.add_argument(
            "--feature-counts-options",
            default=self.options,
            help="""Any extra options for feature counts. Note that the -s
             option (strandness), the -g option (attribute name) and -t options
            (genetic type) have their own options. If you use still use one of
            the -s/-g/-t, it will replace the --feature-counts-strandness,
            --feature-counts-attribute and -feature-counts-feature options respectively""",
        )


class SlurmOptions:
    def __init__(self, group_name="slurm", memory=4000, queue="common", cores=4):
        """

        ::

            class Options(argparse.ArgumentParser, SlurmOptions):
                def __init__(self, prog="whatever")
                    super(Options, self).__init__(usage="todo",
                        prog="whatever",description=""
                    self.add_argument(...)
                    ...
                    self.add_slurm_options()

        """
        self.group_name = group_name
        self.memory = memory
        self.cores = cores
        self.queue = queue

    def add_options(self, parser):
        group = parser.add_argument_group(self.group_name)
        group.add_argument(
            "--slurm-cores-per-job",
            dest="slurm_cores_per_job",
            default=self.cores,
            help="""Number of cores/jobs to be used at the same time.
            Ignored and replaced if a cluster_config.yaml file is part
            of your pipeline (e.g. rnaseq)""",
        )
        group.add_argument(
            "--slurm-queue",
            dest="slurm_queue",
            default=self.queue,
            help="SLURM queue to be used (biomics)",
        )
        group.add_argument(
            "--slurm-memory",
            dest="slurm_memory",
            default=self.memory,
            help="""memory in Mb (default 4000; stands for 4000 Mbytes).
            Ignored and replaced if a cluster_config.yaml file is part
            of your pipeline (e.g. rnaseq)""",
        )
