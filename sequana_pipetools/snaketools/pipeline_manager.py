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
import sys
import os

import colorlog
from sequana_pipetools.misc import PipetoolsException

from .file_factory import FastQFactory, FileFactory
from .module import Module
from .pipeline_utils import OnSuccessCleaner, message
from .sequana_config import SequanaConfig
from deprecated import deprecated

logger = colorlog.getLogger(__name__)


class PipelineManagerBase:
    """

    For all files except FastQ, please use this class instead of
    PipelineManager.

    """

    def __init__(self, name, config, schema=None, matplotlib_backend='Agg'):
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
        self.matplotlib_backend = matplotlib_backend
            
        # some common choices     
        self.sample = "{sample}"
        self.basename = "{sample}/%s/{sample}"

        self.setup()

    def error(self, msg):
        msg = (f"{msg}\nPlease check the content of your config file. "
            "It should have those 3 key/value pairs in config.yaml (adapt to your needs):"
            "\n"
            "- input_directory: path_to_find_input_files\n"
            '- input_readtag: "_R[12]_"\n'
            '- input_pattern: "*.fastq.gz"\n'
            '\n'
            "You must set an input_directory key and an input_pattern key so that files can be found. \n"
            "You may omit input_directory but input_pattern must then correspond to a valid file pattern.\n"
            "You must also set input_readtag to a valid read tag for Illumina data (typically _R[12]_ or _[12]. ; not the trailing dot).\n"
            "If you are not analysing Illumina paired data (e.g., nanopore), let the input_readtag field empty.")
        raise PipetoolsException(msg)

    @deprecated(version="1.0", reason="will be removed in v1.0. Update your pipelines.")
    def getname(self, rulename, suffix=None):
        """In the basename, include rulename and suffix"""
        if suffix is None:
            suffix = ""
        return self.basename % rulename + suffix

    @deprecated(version="1.0", reason="will be removed in v1.0. Update your pipelines.")
    def getwkdir(self, rulename):
        return os.path.join(self.sample, rulename)

    def getrawdata(self):
        """Return list of raw data

        A list of files is returned (one or two files)
        otherwise, a function compatible with snakemake is returned. This function
        contains a wildcard to each of the samples found by the manager.
        """
        if not self.samples:
            raise ValueError(
                "Define the samples attribute as a dictionary with"
                " sample names as keys and the corresponding location as values."
            )
        return lambda wildcards: self.samples[wildcards.sample]

    @deprecated(version="1.0", reason="will be removed in v1.0. Update your pipelines.")
    def message(self, msg):  # pragma: no cover
        message(msg)

    def setup(self, namespace=None, mode="error"):
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

        if self.matplotlib_backend:
            import matplotlib as mpl
            mpl.use(self.matplotlib_backend)

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

    def teardown(self, extra_dirs_to_remove=[], extra_files_to_remove=[], outdir="."):

        # add a Makefile
        cleaner = OnSuccessCleaner(self.name, outdir=outdir)
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


class PipelineManagerDirectory(PipelineManagerBase):
    """Most generic pipeline manager

    Only checks for valid config file and its schema

    For all files except FastQ, please use this class instead of
    PipelineManager.

    """

    def __init__(self, name, config, schema=None):
        super().__init__(name, config, schema)


class PipelineManager(PipelineManagerBase):
    """Utility to manage easily the snakemake pipeline including input files

    Inside a snakefile, use it as follows::

        from sequana import PipelineManager
        manager = PipelineManager("pipeline_name", "config.yaml")

    This will expect some specific fields in the config file::

        - input_directory: path_to_find_input_files
        - input_readtag: "_R[12]_"
        - input_pattern: "*.fastq.gz"

    You may omit the input_readtag, which is not required for non-paired data. For instance for
    pacbio and nanopore files, there are not paired and the read tag is not required. Instead, if
    you are dealing with Illumina/MGI data sets, you must provide this field IF AND ONLY IF you want 
    your data to be processed as paired data (or single end). See later for more details.
    
    You may omit the input_directory but then the input_pattern must match files to be found locally. 
    
    If you set the fastq parameter to True, an error is raised if input_readtag is not provided. 
    This is an extra sanity check for pipelines that handles solely Illumina-like data files.

    In any case, the FileFactory or FastqFactory will provide the samples and their tags in 
    :attr:`samples` where tag are extracted from the sample names where read tags are removed.

    If you have specific wishes to create sample names from the filenames, you may provide a function
    with the :attr:`sample_func` parameter. If so, you must provide the input_directory and input_pattern
    to identify the files to process. For instance, in the sequana_fastqc pipeline, you set the input_directory
    and input_pattern and use this function to extract the sample names
    
        from sequana_pipetools import SequanaManager
        def func(filename):
            return filename.split("/")[-1].split('.', 1)[0]
        pm = SequanaManager("fastqc", "config.yaml", sample_func=func)

    The manager can then easily access to the data with a :class:`FastQFactory`
    instance::

        manager.ff.filenames

    This can be further used to get a wildcards with the proper directory.

    In Sequencing data, the sequences are stored in one file (single-ended) data
    or in two files (paired-data). In both cases, most common sequencers will append
    a so-called read-tag to identify the first and second file. Traditionnally, e.g., 
    with illumina sequencers the read tag are _R1_ and _R2_ or a trailing _1 and _2
    Note that samples names have sometimes this tag included. Consider e.g. 
    sample_replicate_1_R1_.fastq.gz or sample_replicate_1_1.fastq.gz then you can imagine that
    it is tricky to handle.

    The manager tells you if the samples are paired or not assuming all
    samples are homogeneous (either all paired or all single-ended) and a user 
    read_tag that can discrimate the sample name unambigously.

    """

    def __init__(self, name:str, config:str, schema=None, 
            sample_func=None, extra_prefixes_to_strip=[], 
            sample_pattern=None, **kwargs):
        """.. rubric:: Constructor

        :param name: name of the pipeline
        :param config:  name of a configuration file
        :param str schema: YAML file to validate the config file
        :param sample_func: a user-defined function that extract sample names from filenames
        :param list prefixes_to_strip: list of common prefixes that should be stripped from filenames
            to identify sample names
        """
        super().__init__(name, config, schema)

        cfg = SequanaConfig(config)
        cfg.config.pipeline_name = self.name

        # can be provided in the config file or arguments
        self.sample_pattern = cfg.config.get("sample_pattern", sample_pattern)
        self.extra_prefixes_to_strip = cfg.config.get("extra_prefixes_to_strip", extra_prefixes_to_strip)

        # if input_directory is not filled, the input_pattern, if valid, will be used instead and must
        # be provided anyway.
        if "input_pattern" not in cfg.config:
            self.error("The PipelineManager expect the field 'input_pattern' to be in your config file")

        readtag = cfg.config.get("input_readtag", None)
        use_fastq_factory = True if readtag else False

        # input_pattern is required. input_directory may be optional
        # do we have an input_directory ? If so, input_pattern is required
        if "input_directory" in cfg.config and cfg.config.input_directory:
            directory = cfg.config.input_directory.strip()
            if not os.path.isdir(directory):
                self.error(f"The ({directory}) directory does not exist.")
            if cfg.config.input_pattern:
                glob_dir = directory + os.sep + cfg.config.input_pattern
        # otherwise, the input_pattern must be provided (checked above) and valid
        elif cfg.config.input_pattern:
            glob_dir = cfg.config.input_pattern


        # if user set the sample func, no need for fileFactory
        # The config uses the input_directory and input_pattern (compulsary). 
        if sample_func:
            logger.info("Using sample_func function to get sample names as provided by the pipeline/user")
            path = cfg.config["input_directory"]
            pattern = cfg.config["input_pattern"]
            if path.strip():
                pattern = path + os.sep + pattern

            self._get_any_files(pattern)
            # Here, we overwrite the sample name definition from sequana_pipetools to use the
            # function provided by the user.
            self.samples = {sample_func(filename): filename for filename in self.ff.realpaths}
            logger.info(f"Found {len(self.samples)} samples")
        
        elif use_fastq_factory:
            logger.info(f"Using FastQFactory (readtag {readtag})")

            #if not cfg.config.get('input_readtag', ""):
            #    logger.warning("No input_readtag option found in the config file. Since you specify fastq=True, the PipelineManager set it to _R[12]_ for you but we strongly recommend to set it in your config file using input_readtag='_R[12]_'.")
            #    cfg.config.input_readtag = "_R[12]_"
            self._get_fastq_files(glob_dir, cfg.config.input_readtag)
            if self.paired:
                logger.info("Paired data found")
        else:
            logger.info(f"Using FileFactory (no readtag)")
            self._get_any_files(glob_dir)
            logger.info(f"Found {len(self.samples)} samples")
            
        if not self.ff.filenames:
            self.error(f"No files were found with pattern {glob_dir} and read tag {readtag}.")

        # finally, keep track of the config file
        self.config = cfg.config

    def _get_paired(self):
        try:
            return self.ff.paired
        except AttributeError:
            return False

    paired = property(_get_paired)

    def _get_fastq_files(self, glob_dir, read_tag):
        """ """
        self.ff = FastQFactory(glob_dir, read_tag=read_tag, 
            extra_prefixes_to_strip=self.extra_prefixes_to_strip,
            sample_pattern=self.sample_pattern
            )

        # check whether it is paired or not. This is just to raise an error when
        # there is inconsistent mix of R1 and R2
        self.paired

        # samples contains a correspondance between the sample name and the
        # real filename location.
        self.samples = {
            tag: [self.ff.get_file1(tag), self.ff.get_file2(tag)] if self.ff.get_file2(tag) else [self.ff.get_file1(tag)] for tag in self.ff.tags
        }

        if len(self.ff.tags) == 0:
            raise ValueError(
                "Could not find Fastq files files with valid format "
                "(NAME_R1_<SUFFIX>.fastq.gz where <SUFFIX> is "
                "optional"
            )

    def _get_any_files(self, pattern):
        self.ff = FileFactory(pattern,
            extra_prefixes_to_strip=self.extra_prefixes_to_strip,
            sample_pattern=self.sample_pattern)

        # samples contains a correspondance between the sample name and the
        # real filename location.
        self.samples = {tag: fl for tag, fl in zip(self.ff.filenames, self.ff.realpaths)}

    def getrawdata(self):
        """Return list of raw data

        This function contains a wildcard to each of the samples found by the manager.
        """
        return lambda wildcards: self.samples[wildcards.sample]
