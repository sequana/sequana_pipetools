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
import inspect
import shutil
import sys

from sequana_pipetools.snaketools import Pipeline

from .misc import print_version

__all__ = [
    "ClickGeneralOptions",
    "ClickInputOptions",
    "ClickFeatureCountsOptions",
    "ClickKrakenOptions",
    "ClickSlurmOptions",
    "ClickSnakemakeOptions",
    "ClickTrimmingOptions",
    "init_click",
    "include_options_from",
    "OptionEatAll",
]

import rich_click as click
from packaging.version import Version

from sequana_pipetools.info import sequana_epilog, sequana_prolog

_RC_VERSION = Version(click.__version__)

if _RC_VERSION >= Version("1.9.0"):
    # New API introduced in rich_click 1.9 — old names are PendingDeprecationWarning
    click.rich_click.TEXT_MARKUP = "markdown"
    click.rich_click.OPTIONS_TABLE_COLUMN_TYPES = ["required", "opt_short", "opt_long", "help"]
    click.rich_click.OPTIONS_TABLE_HELP_SECTIONS = ["help", "deprecated", "envvar", "default", "required", "metavar"]
else:
    click.rich_click.USE_MARKDOWN = True
    click.rich_click.SHOW_METAVARS_COLUMN = False
    click.rich_click.APPEND_METAVARS_HELP = True

click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.FOOTER_TEXT = sequana_epilog


def init_click(NAME, groups={}):
    """This function populates click variables and groups

    NAME is added to the rich_context so that ClickXXOptions classes
    may reuse it. It also sets the HEADER_TEXT and initiate a
    OPTION_GROUPS to be used by rich_click.

    In a sequana pipeline, you can use this code::

        CTX = init_click(NAME, groups={
                "Pipeline Specific": [
                 "--method-example"],
                 }
            )
        @click.command(context_settings=CONTEXT_SETTINGS)
        @include_options_from(ClickSnakemakeOptions, working_directory=NAME)
        @click.options("--method-example")
        def main(**kwargs):
            pass

    """
    click.rich_click.HEADER_TEXT = sequana_prolog.format(name=NAME)
    click.rich_click.FOOTER_TEXT = sequana_epilog.format(name=NAME)
    click.rich_click.OPTION_GROUPS[f"sequana_{NAME}"] = []

    click.rich_context.RichContext.NAME = NAME

    for name, options in groups.items():
        click.rich_click.OPTION_GROUPS[f"sequana_{NAME}"].append({"name": name, "options": options})

    # a common context for the help
    return dict(help_option_names=["-h", "--help"])


# A decorator to include common set of options
# This decorator also populates the OPTION GROUPS
# dynamically


def include_options_from(cls, *args, **kwargs):
    def decorator(f):
        caller_module = inspect.getmodule(f)
        if caller_module and "NAME" in caller_module.__dict__:
            NAME = caller_module.__dict__["NAME"]
        else:  # pragma: no cover
            print("You must define NAME as your pipeline name in the module main.py ")
            sys.exit(1)

        # add options dynamically to the main click command
        for option in cls(*args, **kwargs).options:
            option(f)

        # add groups dynamically to the OPTION_GROUPS
        # NAME = kwargs.get("caller", None)
        click.rich_click.OPTION_GROUPS.setdefault(f"sequana_{NAME}", []).insert(0, cls.metadata)

        return f

    return decorator


# This is a recipe from https://stackoverflow.com/questions/48391777/nargs-equivalent-for-options-in-click
# to allow command line such as
# sequana_multitax --databases 1 2 3
class OptionEatAll(click.Option):
    def __init__(self, *args, **kwargs):
        self.save_other_options = kwargs.pop("save_other_options", True)
        nargs = kwargs.pop("nargs", -1)
        if nargs != -1:
            raise ValueError("nargs, if set, must be -1 not {}".format(nargs))
        super(OptionEatAll, self).__init__(*args, **kwargs)
        self._previous_parser_process = None
        self._eat_all_parser = None

    def add_to_parser(self, parser, ctx):
        def parser_process(value, state):
            # method to hook to the parser.process
            done = False
            value = [value]
            if self.save_other_options:
                # grab everything up to the next option
                while state.rargs and not done:
                    for prefix in self._eat_all_parser.prefixes:
                        if state.rargs[0].startswith(prefix):
                            done = True
                    if not done:
                        value.append(state.rargs.pop(0))
            else:
                # grab everything remaining
                value += state.rargs
                state.rargs[:] = []
            value = tuple(value)

            # call the actual process
            self._previous_parser_process(value, state)

        retval = super(OptionEatAll, self).add_to_parser(parser, ctx)
        for name in self.opts:
            our_parser = parser._long_opt.get(name) or parser._short_opt.get(name)
            if our_parser:
                self._eat_all_parser = our_parser
                self._previous_parser_process = our_parser.process
                our_parser.process = parser_process
                break
        return retval


class ClickGeneralOptions:
    group_name = "General"
    metadata = {
        "name": group_name,
        "options": ["--deps", "--from-project", "--help", "--level", "--version"],
    }

    def __init__(self, caller=None):
        self.options = [
            click.option(
                "--deps", is_flag=True, callback=self.deps_callback, help="Show the known dependencies of the pipeline"
            ),
            click.option(
                "--from-project",
                "from_project",
                type=click.Path(),
                callback=self.from_project_callback,
                help="""You can initiate a new analysis run from an existing project.
                    In theory, sequana project have a hidden .sequana directory,
                    which can be used as input. The name of the run directory itself
                    should suffice (if .sequana is found inside). From there,
                    the config file and the pipeline files are copied in your new
                    working directory""",
            ),
            click.option(
                "--level",
                "level",
                default="INFO",
                type=click.Choice(["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"]),
                help="Logging level",
            ),
            click.option(
                "-v", "--version", is_flag=True, callback=self.version_callback, help="Print the version and exit"
            ),
        ]

    @staticmethod
    def version_callback(ctx, param, value):
        if not value:
            return
        print_version(ctx.NAME)
        ctx.exit(0)

    @staticmethod
    def from_project_callback(ctx, param, value):
        if not value:
            return
        else:
            # When --from-project is called, all value of arguments are replaced by the ones
            # found in the config file. Therefore, users may ommit all arguments. However, some
            # may be compulsary, so we need to reset all 'required' arguments to False
            for option in ctx.command.params:
                option.required = False
            return value

    @staticmethod
    def deps_callback(ctx, param, value):
        if not value:
            return

        module = Pipeline(ctx.NAME)
        with open(str(module.requirements), "r") as fin:
            data = fin.read()
        data = data.split()
        data = "\n".join(sorted(data))
        click.echo(
            f"sequana_{ctx.NAME} will need one or more of these software to work correctly. We recommend you to use --apptainer-prefix to enable containers so that you do not need to install them manually:\n\n{data}\n"
        )
        ctx.exit(0)


def guess_scheduler():
    """Guesses whether we are on a SLURM cluster or not.

    If not, we assume a local run is expected.
    """

    if shutil.which("sbatch") and shutil.which("srun"):  # pragma: no cover
        return "slurm"
    else:
        return "local"


class ClickSnakemakeOptions:
    group_name = "Snakemake"
    metadata = {
        "name": group_name,
        "options": [
            "--apptainer-prefix",
            "--apptainer-args",
            "--no-md5-check",
            "--force",
            "--jobs",
            "--keep-going",
            "--monitor",
            "--execute",
            "--working-directory",
        ],
    }

    def __init__(self, working_directory="analysis", caller=None):
        self.workdir = working_directory

        _default_jobs = 40 if guess_scheduler() == "slurm" else 4

        self.options = [
            click.option(
                "--apptainer-prefix",
                "apptainer_prefix",
                default=None,
                show_default=True,
                type=click.Path(),
                help="""Path to a directory where Apptainer/Singularity images are stored (or will be downloaded). Recommended to avoid redundant downloads across projects.""",
            ),
            click.option(
                "--apptainer-args",
                "apptainer_args",
                default="",
                show_default=True,
                help="""Extra arguments passed to apptainer/singularity exec (e.g. bind mounts). By default, -B $HOME:$HOME is set.""",
            ),
            click.option(
                "--no-md5-check",
                "no_md5_check",
                is_flag=True,
                default=False,
                help="""Skip MD5 checksum verification of existing containers against the damona registry. By default, existing containers are verified and re-downloaded if corrupted.""",
            ),
            click.option(
                "--force",
                "force",
                is_flag=True,
                default=False,
                help="""If the working directory exists, proceed anyway.""",
            ),
            click.option(
                "--jobs",
                "jobs",
                default=_default_jobs,
                show_default=True,
                help="""Number of jobs to run in parallel (passed to Snakemake --jobs). Defaults to 4 for local runs and 40 on a SLURM cluster.""",
            ),
            click.option(
                "--keep-going",
                "keep_going",
                is_flag=True,
                default=False,
                help="""If set, snakemake will keep running independent jobs even if some fail (--keep-going flag).""",
            ),
            click.option(
                "--monitor",
                "monitor",
                is_flag=True,
                default=False,
                help="""Enable a live rich progress display while the pipeline runs.
                    Watches logs/<rule>/<sample>.log files to track per-step progress.
                    Requires an interactive terminal; silently falls back to plain
                    snakemake output otherwise.""",
            ),
            click.option(
                "--use-apptainer",
                "use_apptainer",
                is_flag=True,
                default=False,
                hidden=True,
                is_eager=True,
                expose_value=True,
                callback=lambda ctx, param, value: (
                    click.echo(
                        "WARNING: --use-apptainer is deprecated and has no effect.\n"
                        "Use --apptainer-prefix to enable apptainer/singularity containers.",
                        err=True,
                    )
                    if value
                    else None
                ),
                help="""[DEPRECATED] Use --apptainer-prefix instead.""",
            ),
            click.option(
                "--execute",
                "execute",
                is_flag=True,
                default=False,
                help="""Execute the pipeline immediately after the working directory is prepared. Intended for automation and scripting; interactive users should review config.yaml first.""",
            ),
            click.option(
                "--working-directory",
                "workdir",
                default=self.workdir,
                show_default=True,
                help="""Directory where the pipeline configuration and results will be saved.""",
            ),
        ]


class ClickInputOptions:
    group_name = "Data"
    metadata = {
        "name": group_name,
        "options": ["--input-directory", "--input-pattern", "--input-readtag", "--exclude-pattern"],
    }

    def __init__(
        self, input_directory=".", input_pattern="*fastq.gz", add_input_readtag=True, caller=None, exclude_pattern=None
    ):
        self.input_directory = input_directory
        self.input_pattern = input_pattern
        self.exclude_pattern = exclude_pattern
        self.add_input_readtag = add_input_readtag

        self.options = [
            click.option(
                "--input-directory",
                "input_directory",
                default=self.input_directory,
                type=click.Path(exists=True, file_okay=False),
                # required=True,
                show_default=True,
                help="""Where to find the input files""",
            ),
            click.option(
                "--input-pattern",
                "input_pattern",
                default=self.input_pattern,
                type=click.STRING,
                show_default=True,
                help=f"pattern for the input files ({input_pattern})",
            ),
            click.option(
                "--exclude-pattern",
                "exclude_pattern",
                default=self.exclude_pattern,
                type=click.STRING,
                show_default=True,
                help=f"pattern for excluding input files ({exclude_pattern})",
            ),
        ]

        if self.add_input_readtag:
            self.options.append(
                click.option(
                    "--input-readtag",
                    "input_readtag",
                    default="_R[12]_",
                    show_default=True,
                    type=click.STRING,
                    help="""pattern for the paired/single end FastQ. If your files are
                    tagged with _R1_ or _R2_, please set this value to '_R[12]_'. If your
                    files are tagged with  _1 and _2, you must change this readtag
                    accordingly to '_[12]'.""",
                )
            )


class ClickKrakenOptions:
    group_name = "Kraken"
    metadata = {
        "name": group_name,
        "options": [
            "--kraken-databases",
            "--skip-kraken",
        ],
    }

    def __init__(self, caller=None):
        self.options = [
            click.option(
                "--kraken-databases",
                "kraken_databases",
                type=click.STRING,
                nargs="+",
                help="""Path to a valid set of Kraken database(s).
                    If you do not have any, please see https://sequana.readthedocs.io
                    or use sequana_taxonomy --download option.
                    You may use several, in which case, an iterative taxonomy is
                    performed as explained in online sequana documentation""",
            ),
            click.option(
                "--skip-kraken",
                is_flag=True,
                default=False,
                show_default=True,
                help="""Skip the Kraken taxonomy step.""",
            ),
        ]


class ClickTrimmingOptions:
    group_name = "Trimming"
    metadata = {
        "name": group_name,
        "options": [
            "--software-choice",
            "--trimming-minimum-length",
            "--trimming-adapter-read1",
            "--trimming-adapter-read2",
            "--disable-trimming",
            "--trimming-cutadapt-mode",
            "--trimming-cutadapt-options",
            "--trimming-quality",
        ],
    }

    def __init__(self, software=["cutadapt", "atropos", "fastp"], caller=None):
        """This section is dedicated to reads trimming and filtering and adapter
        trimming. We currently provide supports for Cutadapt/Atropos and FastP tools.

        This section uniformizes the options for such tools


        """

        self.software = software
        self.software_default = "fastp" if "fastp" in software else software[0]

        def quality(x):
            x = int(x)
            if x < 0 and x != -1:
                click.BadParameter("quality must be positive")
            return x

        self.options = [
            click.option(
                "--software-choice",
                "trimming_software_choice",
                default=self.software_default,
                show_default=True,
                type=click.Choice(self.software),
                help="""Trimming software to use.""",
            ),
            click.option("--disable-trimming", is_flag=True, default=False, help="Disable the trimming step entirely."),
            click.option(
                "--trimming-adapter-read1",
                "trimming_adapter_read1",
                default="",
                show_default=True,
                help="""Adapter sequence for read1. fastp auto-detects adapters; use this to override for fastp or cutadapt/atropos.""",
            ),
            click.option(
                "--trimming-adapter-read2",
                "trimming_adapter_read2",
                default="",
                show_default=True,
                help="""Adapter sequence for read2. fastp auto-detects adapters; use this to override for fastp or cutadapt/atropos.""",
            ),
            click.option(
                "--trimming-minimum-length",
                default=20,
                show_default=True,
                help="""minimum number of bases required; read discarded
                    otherwise. For cutadapt, default is 20 and for fastp, 15. We set it to 20.""",
            ),
            click.option(
                "--trimming-quality",
                "trimming_quality",
                default=-1,
                show_default=True,
                type=quality,
                help="""Trimming quality parameter depends on the algorithm used by
                    the software behind the scene and may vary greatly; consequently, we do not provide
                    a default value. Cutadapt uses 30 by default, fastp uses 15 by default. If
                    unset, the rnaseq pipeline set the default to 30 for cutadapt and 15 for fastp. """,
            ),
            click.option(  # Cutadapt specific
                "--trimming-cutadapt-mode",
                "trimming_cutadapt_mode",
                default="b",
                show_default=True,
                type=click.Choice(["g", "a", "b"]),
                help="""Mode used to remove adapters. g for 5', a for 3', b for both
                        5'/3' as defined in cutadapt documentation""",
            ),
            click.option(
                "--trimming-cutadapt-options",
                "trimming_cutadapt_options",
                default=" -O 6 --trim-n",
                show_default=True,
                help="""additional options understood by cutadapt. Here, we trim the
                        Ns; -O 6 is the minimum overlap length between read and adapter for an adapter
                        to be found""",
            ),
        ]


class ClickFeatureCountsOptions:
    group_name = "Feature Counts"
    metadata = {
        "name": group_name,
        "options": [
            "--feature-counts-strandness",
            "--feature-counts-attribute",
            "--feature-counts-extra-attributes",
            "--feature-counts-feature-type",
            "--feature-counts-options",
        ],
    }

    def __init__(self, feature_type="gene", attribute="ID", options=None, strandness=None, caller=None):
        self.feature_type = feature_type
        self.attribute = attribute
        self.options = options
        self.strandness = strandness

        self.options = [
            click.option(
                "--feature-counts-strandness",
                default=self.strandness,
                help="""0 for unstranded, 1 for stranded and 2 for reversely
                stranded. If you do not know, let the pipeline guess for you.""",
            ),
            click.option(
                "--feature-counts-attribute",
                default=self.attribute,
                help="""the GFF attribute to use as identifier. If you do not know,
                look at the GFF file or use 'sequana summary YOURFILE.gff' command to get
                information about attributes and  features contained in your annotation file.""",
            ),
            click.option(
                "--feature-counts-extra-attributes",
                default=None,
                help="""Extra GFF attribute(s) to include in the feature counts output (comma-separated).""",
            ),
            click.option(
                "--feature-counts-feature-type",
                default=self.feature_type,
                help="""GFF feature type to count (e.g. gene, exon, mRNA). Use 'sequana summary YOURFILE.gff' to inspect available types. For multiple features, provide comma-separated values or see https://github.com/sequana/rnaseq/wiki.""",
            ),
            click.option(
                "--feature-counts-options",
                default=self.options,
                help="""Extra options passed directly to featureCounts. Note: -s (strandness), -g (attribute) and -t (feature type) are already handled by their own flags above and will be overridden if repeated here.""",
            ),
        ]


class ClickSlurmOptions:
    group_name = "Slurm"
    metadata = {
        "name": group_name,
        "options": ["--profile", "--slurm-queue", "--slurm-memory"],
    }

    def __init__(self, memory="4G", queue="common", profile=None, caller=None):
        self.memory = memory
        self.queue = queue
        self.profile = guess_scheduler()

        self.options = [
            click.option(
                "--profile",
                "profile",
                default=self.profile,
                show_default=True,
                type=click.Choice(["local", "slurm"]),
                help="Execution profile: 'local' for a workstation, 'slurm' for an HPC cluster.",
            ),
            click.option(
                "--slurm-memory",
                "slurm_memory",
                default=self.memory,
                show_default=True,
                help="""Memory requested per SLURM job (e.g. 4G, 16G).""",
            ),
            click.option(
                "--slurm-queue",
                "slurm_queue",
                default=self.queue,
                show_default=True,
                help="SLURM partition/queue name to submit jobs to.",
            ),
        ]
