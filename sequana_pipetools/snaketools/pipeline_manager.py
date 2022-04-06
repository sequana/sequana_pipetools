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
from sequana_pipetools.misc import PipetoolsException

from .file_factory import FastQFactory, FileFactory
from .module import Module
from .pipeline_utils import OnSuccessCleaner, message
from .sequana_config import SequanaConfig

logger = colorlog.getLogger(__name__)


class PipelineManagerBase:
    """

    For all files except FastQ, please use this class instead of
    PipelineManager.

    """

    def __init__(self, name, config, schema=None):
        # Make sure the config is valid
        self.name = name
        cfg = SequanaConfig(config)
        if schema:
            if not cfg.check_config_with_schema(schema):
                raise PipetoolsException("Please check the config file, some mandatory values are missing.")

        # Used by the dynamic rules to defined the location where to copy
        # dynamic rules.
        self.pipeline_dir = os.getcwd() + os.sep

        # Populate the config with additional information
        self.config = cfg.config
        self.config.pipeline_name = name

        self.setup()

    def error(self, msg):
        msg += "\nPlease check the content of your config file. You must have input_directory set, or input_pattern."
        raise PipetoolsException(msg)

    def getname(self, rulename, suffix=None):
        """In the basename, include rulename and suffix"""
        print("//DEPRECATED. please replace getname() by a string")
        if suffix is None:
            suffix = ""
        return self.basename % rulename + suffix

    def getwkdir(self, rulename):
        print("//DEPRECATED. please replace getwkdir() by a string")
        return os.path.join(self.sample, rulename)

    def getrawdata(self):
        """Return list of raw data

        If :attr:`mode` is *nowc*, a list of files is returned (one or two files)
        otherwise, a function compatible with snakemake is returned. This function
        contains a wildcard to each of the samples found by the manager.
        """
        if not self.samples:
            raise ValueError(
                "Define the samples attribute as a dictionary with"
                " sample names as keys and the corresponding location as values."
            )
        return lambda wildcards: self.samples[wildcards.sample]

    def message(self, msg):  # pragma: no cover
        print("//DEPRECATED. We'll be removed in version >0.8")
        message(msg)

    def setup(self, namespace=None, mode="error", matplotlib="Agg"):
        """

        90% of the errors come from the fact that users did not set a matplotlib
        backend properly. In the setup() function, we set the backend to Agg on
        purpose. One can set this parameter to None to avoid this behaviour
        """
        # The rulegraph wrapper expected manager.snakefile, which is defined here
        # Note also that the snakefile path when called from the rulegraph directory
        # has an extra 'rulegraph' in the path that is removed here.
        self._snakefile = os.path.abspath(self.name + ".rules").replace("rulegraph/", "")

        try:
            # check requirements if possible. This is the standalone application
            # requirements, not the files possibly provided in the config file
            Module(self.name).check("warning")
        except ValueError:
            pass

        if matplotlib:
            import matplotlib as mpl

            mpl.use(matplotlib)

    def _get_snakefile(self):
        return self._snakefile

    snakefile = property(_get_snakefile)

    def clean_multiqc(self, filename):
        with open(filename, "r") as fin:
            with open(filename + "_tmp_", "w") as fout:
                line = fin.readline()
                while line:
                    if """<a href="http://multiqc.info" target="_blank">""" in line:
                        line = fin.readline()  # read the image
                        line = fin.readline()  # read the ending </a> tag
                    else:
                        fout.write(line)
                    line = fin.readline()  # read the next line
        import shutil

        shutil.move(filename + "_tmp_", filename)

    def teardown(self, extra_dirs_to_remove=[], extra_files_to_remove=[]):

        # add a Makefile
        cleaner = OnSuccessCleaner(self.name)
        cleaner.directories_to_remove.extend(extra_dirs_to_remove)
        cleaner.files_to_remove.extend(extra_files_to_remove)
        cleaner.add_makefile()

    def get_html_summary(self, float="left", width=30):
        import pandas as pd
        import pkg_resources

        vers = pkg_resources.require("sequana_{}".format(self.name))[0].version

        data = {"samples": len(self.samples), "sequana_{}_version".format(self.name): vers}
        try:
            data["paired"] = self.paired
        except AttributeError:
            pass

        df_general = pd.DataFrame(
            data,
            index=["summary"],
        )

        from sequana.utils.datatables_js import DataTable

        datatable = DataTable(df_general.T, "general", index=True)
        datatable.datatable.datatable_options = {
            "paging": "false",
            "bFilter": "false",
            "bInfo": "false",
            "header": "false",
            "bSort": "true",
        }
        js = datatable.create_javascript_function()
        htmltable = datatable.create_datatable(style="width: 20%; float:left")
        contents = """<div style="float:{}; width:{}%">{}</div>""".format(float, width, js + htmltable)
        return contents


class PipelineManagerGeneric(PipelineManagerBase):
    """This pipeline identifies all files that match the input pattern using the
    FileFactory class.

    Each sample name is a unique ID.
    This is not very convenient so, one can pass a function
    to extract e.g. the filename as the unique key

    def func(filename):
        return filename.split("/")[-1].split('.', 1)[0]

    """

    def __init__(self, name, config, sample_func=None, schema=None):
        super(PipelineManagerGeneric, self).__init__(name, config, schema)

        cfg = SequanaConfig(config)

        # Default mode is the input directory .
        if "input_directory" not in cfg.config.keys():
            self.error("input_directory must be found in the config.yaml file")
        if "input_pattern" not in cfg.config.keys():
            self.error("input_pattern must be found in the config.yaml file")

        path = cfg.config["input_directory"]
        pattern = cfg.config["input_pattern"]

        if path.strip():
            self.ff = FileFactory(path + os.sep + pattern)
        else:
            self.ff = FileFactory(pattern)
        L = len(self.ff)
        if L == 0:
            logger.warning("No files found with the pattern {}".format(pattern))
        else:
            logger.info("Found {} files matching your requests".format(L))

        # samples contains a correspondance between the sample name and the
        # real filename location.
        self.sample = "{sample}"
        self.basename = "{sample}/%s/{sample}"

        self.samples = None
        if sample_func:
            try:
                self.samples = {sample_func(filename): filename for filename in self.ff.realpaths}
            except Exception:
                pass
        else:
            self.samples = {str(i + 1): filename for i, filename in enumerate(self.ff.realpaths)}


class PipelineManagerDirectory(PipelineManagerBase):
    """

    For all files except FastQ, please use this class instead of
    PipelineManager.

    """

    def __init__(self, name, config, schema=None):
        super().__init__(name, config, schema)


class PipelineManager(PipelineManagerGeneric):
    """Utility to manage easily the snakemake pipeline

    Inside a snakefile, use it as follows::

        from sequana import PipelineManager
        manager = PipelineManager("pipeline_name", "config.yaml")

    config file must have these fields::

        - input_directory:  # a_path
        - input_readtag: _R[12]_ # default
        - input_pattern:    # a_global_pattern e.g. H*fastq.gz

    The manager can then easily access to the data with a :class:`FastQFactory`
    instance::

        manager.ff.filenames

    This can be further used to get a wildcards with the proper directory.

    The manager also tells you if the samples are paired or not assuming all
    samples are homogneous (either all paired or all single-ended).

    If there is only one sample, the attribute :attr:`mode` is set to "nowc"
    meaning no wildcard. Otherwise, we assume that we are in a wildcard mode.

    When the mode is set, two attributes are also set: :attr:`sample` and
    :attr:`basename`.

    If the mode is **nowc**, the *sample* and *basename* are hardcoded to
    the sample name and  sample/rule/sample respectively. Whereas in the
    **wc** mode, the sample and basename are wildcard set to "{sample}"
    and "{sample}/rulename/{sample}". See the following methods :meth:`getname`.

    For developers: the config attribute should be used as getter only.

    """

    def __init__(self, name, config, pattern="*.fastq.gz", fastq=True, schema=None):
        """.. rubric:: Constructor

        :param name: name of the pipeline
        :param config:  name of a configuration file
        :param pattern: a default pattern if not provided in the configuration
            file as an *input_pattern* field.
        """
        super().__init__(name, config, schema)

        cfg = SequanaConfig(config)
        cfg.config.pipeline_name = self.name
        self.pipeline_dir = os.getcwd() + os.sep

        # First, one may provide the input_directory field
        if cfg.config.input_directory:
            directory = cfg.config.input_directory.strip()
            if not os.path.isdir(directory):
                self.error(f"The ({directory}) directory does not exist.")
            if cfg.config.input_pattern:
                glob_dir = directory + os.sep + cfg.config.input_pattern
            else:
                glob_dir = directory + os.sep + pattern
        # otherwise, the input_pattern can be used
        elif cfg.config.input_pattern:
            glob_dir = cfg.config.input_pattern
        # finally, if none were provided, this is an error
        else:
            self.error("No valid input provided in the config file")

        logger.debug("Input data{}".format(glob_dir))

        if "input_readtag" not in cfg.config:
            logger.warning("No input_readtag option found in the config file. Set to _R[12]_ for you")
            # .input_readtag:
            cfg.config.input_readtag = "_R[12]_"

        if fastq:
            self._get_fastq_files(glob_dir, cfg.config.input_readtag)
        else:
            self._get_bam_files(glob_dir)
        # finally, keep track of the config file
        self.config = cfg.config

    def _get_paired(self):
        return self.ff.paired

    paired = property(_get_paired)

    def _get_fastq_files(self, glob_dir, read_tag):
        """ """
        self.ff = FastQFactory(glob_dir, read_tag=read_tag)
        if self.ff.filenames == 0:
            self.error(f"No files were found with pattern {glob_dir} and read tag {read_tag}.")

        # check whether it is paired or not. This is just to raise an error when
        # there is inconsistent mix of R1 and R2
        self.paired

        ff = self.ff  # an alias
        # samples contains a correspondance between the sample name and the
        # real filename location.
        self.samples = {
            tag: [ff.get_file1(tag), ff.get_file2(tag)] if ff.get_file2(tag) else [ff.get_file1(tag)] for tag in ff.tags
        }

        if len(ff.tags) == 0:
            raise ValueError(
                "Could not find fastq.gz files with valid format "
                "(NAME_R1_<SUFFIX>.fastq.gz where <SUFFIX> is "
                "optional"
            )
        else:
            self.sample = "{sample}"
            self.basename = "{sample}/%s/{sample}"

    def _get_bam_files(self, pattern):
        ff = FileFactory(pattern)
        # samples contains a correspondance between the sample name and the
        # real filename location.
        self.samples = {tag: fl for tag, fl in zip(ff.filenames, ff.realpaths)}
        self.sample = "{sample}"
        self.basename = "{sample}/%s/{sample}"

    def getrawdata(self):
        """Return list of raw data

        If :attr:`mode` is *nowc*, a list of files is returned (one or two files)
        otherwise, a function compatible with snakemake is returned. This function
        contains a wildcard to each of the samples found by the manager.
        """
        return lambda wildcards: self.samples[wildcards.sample]
