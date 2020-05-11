# -*- coding: utf-8 -*-
#
#  This file is part of Sequana_pipetools software (Sequana project)
#
#  Copyright (c) 2020 - Sequana Development Team
#
#  File author(s):
#      Thomas Cokelaer <thomas.cokelaer@pasteur.fr>
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
import sys
from sequana_pipetools.misc import Colors, print_version


__all__ = ["GeneralOptions", "SlurmOptions", "SnakemakeOptions",
    "CutadaptOptions", "KrakenOptions", "InputOptions", ]




def init_pipeline(NAME):
    """A function to provide --version and --deps for all pipelines

    """

    if "--version" in sys.argv:
        print_version(NAME)
        sys.exit(0)

    if "--deps" in sys.argv:
        from sequana.snaketools import Module
        module = Module(NAME)
        with open(module.requirements, "r") as fin:
            data = fin.read()
        print("Those software will be required for the pipeline to work correctly:\n{}".format(data))
        sys.exit(0)


class GeneralOptions():
    def __init__(self):
        pass

    def add_options(self, parser):
        parser.add_argument(
            "--run-mode",
            dest="run_mode",
            default=None,
            choices=['local', 'slurm'],
            help="""run_mode can be either 'local' or 'slurm'. Use local to
                run the pipeline locally, otherwise use 'slurm' to run on a
                cluster with SLURM scheduler. Other clusters are not maintained.
                However, you can set to slurm and change the output shell script
                to fulfill your needs. If unset, sequana searches for the sbatch
                and srun commands. If found, this is set automatically to
                'slurm', otherwise to 'local'.
                """)

        parser.add_argument("--version", action="store_true",
            help="Print the version and quit")
        parser.add_argument("--deps", action="store_true",
            help="Show the known dependencies of the pipeline")
        parser.add_argument("--level", dest="level", default="INFO",
            choices=['INFO', 'DEBUG', 'WARNING', 'ERROR', 'CRITICAL'],
            help="logging level in INFO, DEBUG, WARNING, ERROR, CRITICAL")


def guess_scheduler():
    """Guesses whether we are on a SLURM cluster or not.

    If not, we assume a local run is expected.
    """
    from easydev import cmd_exists
    if cmd_exists("sbatch") and cmd_exists("srun"):
        return 'slurm'
    else:
        return 'local'



class SnakemakeOptions():
    def __init__(self, group_name="snakemake", working_directory="analysis"):
        self.group_name = group_name
        self.workdir = working_directory

    def _default_jobs(self):
        if guess_scheduler() == "slurm":
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
                of Snakemake"""
        )
        group.add_argument(
            "--working-directory",
            dest="workdir",
            default=self.workdir,
            help="""where to save the pipeline and its configuration file and
            where the analyse can be run"""
        )
        group.add_argument(
            "--force",
            dest="force",
            action="store_true",
            default=False,
            help="""If the working directory exists, proceed anyway."""
        )




class InputOptions():
    def __init__(self, group_name="data", input_directory=".",
                 input_pattern="*fastq.gz", add_input_readtag=True,
                 add_is_paired=True):
        """

        By default, single-end data sets. If paired, set is_paired to True
        If so, the add_input_readtag must be set
        """
        self.group_name = group_name
        self.input_directory = input_directory
        self.input_pattern = input_pattern
        self.add_is_paired = add_is_paired
        self.add_input_readtag = add_input_readtag

    def add_options(self, parser):
        self.group = parser.add_argument_group(self.group_name)
        self.group.add_argument(
             "--input-directory",
             dest="input_directory",
             default=self.input_directory,
             #required=True,
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

        if self.add_is_paired:
            self.group.add_argument(
                "--paired-data",
                dest="paired_data",
                action="store_true",
                help="""NOT IMPLEMENTED YET"""
            )


class KrakenOptions():
    def __init__(self, group_name="section_kraken"):
        self.group_name = group_name

    def add_options(self, parser):
        group = parser.add_argument_group(self.group_name)

        group.add_argument("--skip-kraken", action="store_true",
            default=False,
            help="""If provided, kraken taxonomy is performed. A database must be
                provided (see below). """)

        group.add_argument("--kraken-databases", dest="kraken_databases", type=str,
            nargs="+", default=[],
            help="""Path to a valid set of Kraken database(s).
                If you do not have any, please see https://sequana.readthedocs.io
                or use sequana_taxonomy --download option.
                You may use several, in which case, an iterative taxonomy is
                performed as explained in online sequana documentation""")


class CutadaptOptions():
    description = """
    This section allows you to trim bases (--cutadapt-quality) with poor
    quality and/or remove adapters.

    To remove adapters, several options are possible:

    (1) you may use an experimental design file (--cutadapt-design-file),
    in which case the type of adapters is also required with the option
    --cutadapt-adapter-choice.
    (2) specify the name of the adapters(--cutadapt-adapter-choice)
    e.g. PCRFree. You may specify "universal" to remove universal
    adapters only.
    (3) provide the adapters directly as a string (or a file) using
    --cutadapt-fwd (AND --cutadapt-rev" for paired-end data).

    If you set the --cutadapt-adapter-choice to 'none', fwd and reverse
    adapters are set to XXXX (see cutadapt documentation).

    """

    adapters_choice = ["none", "universal", "Nextera", "Rubicon", "PCRFree",
        "TruSeq", "SMARTer", "Small"]

    def __init__(self, group_name="section_cutadapt"):
        self.group_name = group_name

    def add_options(self, parser):

        group = parser.add_argument_group(self.group_name, self.description)

        group.add_argument("--skip-cutadapt", action="store_true",
            default=False,
             help="If provided, fastq cleaning and trimming will be skipped")

        group.add_argument("--cutadapt-fwd", dest="cutadapt_fwd",
            default="",
            help="""Provide a adapter as a string of stored in a
                FASTA file. If the file exists, we will store it as expected
                with a preceeding prefix 'file:'""")

        group.add_argument("--cutadapt-rev", dest="cutadapt_rev",
            default="",
            help="""Provide a adapter as a string of stored in a
                FASTA file. If the file exists, we will store it as expected
                with a preceeding prefix 'file:'""")

        def quality(x):
            x = int(x)
            if x < 0:
                raise argparse.ArgumentTypeError("quality must be positive")
            return x

        group.add_argument("--cutadapt-quality", dest="cutadapt_quality",
            default=30, type=quality,
            help="""0  means no trimming, 30 means keep bases with quality
                above 30""")

        group.add_argument("--cutadapt-tool-choice", dest="cutadapt_tool_choice",
            default="cutadapt", choices=["cutadapt", "atropos"],
            help="Select the prefered tool. Default is cutadapt")

        group.add_argument("--cutadapt-adapter-choice",
            dest="cutadapt_adapter_choice",
            default=None, choices=self.adapters_choice,
            help="""Select the adapters used that may possibly still be
                present in the sequences""")

        group.add_argument("--cutadapt-design-file", dest="cutadapt_design_file",
            default=None,
            help="A valid CSV file with mapping of adapter index and sample name")

        group.add_argument("--cutadapt-mode", dest="cutadapt_mode",
            default="b", choices=["g", "a", "b"],
            help="""Mode used to remove adapters. g for 5', a for 3', b for both
                5'/3' as defined in cutadapt documentation""")

        group.add_argument("--cutadapt-options", dest="cutadapt_options",
            default=" -O 6 --trim-n",
            help="""additional options understood by cutadapt""")

    def check_options(self, options):
        """
        """
        design = options.cutadapt_design_file
        adapter_choice = options.cutadapt_adapter_choice
        adapter_fwd = options.cutadapt_fwd
        adapter_rev = options.cutadapt_rev

        if design:
            if adapter_fwd or adapter_rev:
                logger.critical(
                    "When using --cutadapt-design-file, one must not"
                    " set the forward/reverse adapters with --cutadapt-fwd"
                    " and/or --cutadapt-rev\n\n" + self.description)
                sys.exit(1)

            # otherwise, we just check the format but we need the adapter choice
            if options.cutadapt_adapter_choice in [None, 'none']:
                logger.critical(
                    "When using --cutadapt-design-file, you must also"
                    " provide the type of adapters using --cutadapt-adapter-choice"
                    " (set to one of %s )" % self.adapters_choice)
                sys.exit(1)
            from sequana import FindAdaptersFromDesign
            fa = FindAdaptersFromDesign(design, options.cutadapt_adapter_choice)
            try:
                fa.check()
            except:
                logger.critical("Your design file contains indexes not found "
                    "in the list of adapters from {}".format(options.cutadapt_adapter_choice))
                sys.exit(1)

        # No design provided here below
        # do we need to remove adapters at all ?
        elif options.cutadapt_adapter_choice == "none":
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
                    AdapterReader(options.cutadapt_fwd)
                    options.cutadapt_fwd = "file:{}".format(
                        os.path.abspath(options.cutadapt_fwd))
            if options.cutadapt_rev:
                # Could be a string or a file. If a file, check the format
                if os.path.exists(options.cutadapt_rev):
                    AdapterReader(options.cutadapt_rev)
                    options.cutadapt_rev = "file:{}".format(
                        os.path.abspath(options.cutadapt_rev))
        elif options.cutadapt_adapter_choice:
            # nothing to do, the cutadapt rules from sequana will use 
            # the adapter_choice, and fill the fwd/rev automatically
            pass





class SlurmOptions():
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


