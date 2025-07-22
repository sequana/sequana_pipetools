

.. image:: https://badge.fury.io/py/sequana-pipetools.svg
    :target: https://pypi.python.org/pypi/sequana_pipetools

.. image:: https://github.com/sequana/sequana_pipetools/actions/workflows/main.yml/badge.svg?branch=main
    :target: https://github.com/sequana/sequana_pipetools/actions/workflows/main.yml

.. image:: https://coveralls.io/repos/github/sequana/sequana_pipetools/badge.svg?branch=main
    :target: https://coveralls.io/github/sequana/sequana_pipetools?branch=main

.. image:: https://readthedocs.org/projects/sequana-pipetools/badge/?version=latest
    :target: https://sequana-pipetools.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://app.codacy.com/project/badge/Grade/9031e4e4213e4e57a876fd5b792b5003
   :target: https://app.codacy.com/gh/sequana/sequana_pipetools/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade

.. image:: https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11-blue
    :target: https://www.python.org/
    :alt: Python versions

.. image:: http://joss.theoj.org/papers/10.21105/joss.00352/status.svg
   :target: http://joss.theoj.org/papers/10.21105/joss.00352
   :alt: JOSS (journal of open source software) DOI



:Overview: A set of tools to help building or using Sequana pipelines
:Status: Production
:Issues: Please fill a report on `github <https://github.com/sequana/sequana_pipetools/issues>`__
:Citation: Cokelaer et al, (2017), ‘Sequana’: a Set of Snakemake NGS pipelines, Journal of Open Source Software, 2(16), 352,  `JOSS DOI doi:10.21105/joss.00352 <http://www.doi2bib.org/bib/10.21105%2Fjoss.00352>`_

🔧 Installation
===============

from pypi website::

    pip install sequana_pipetools

No dependencies for this package except Python itself. In practice, this package
has no interest if not used within a Sequana pipeline. It is installed automatically when you install
a Sequana pipelines. For example::

    pip install sequana_rnaseq
    pip install sequana_fastqc

See `Sequana <https://sequana.readthedocs.io>`_ for a list of pipelines ready for production.


🎯 Targetted audience
=========================

This package is intended for `Sequana <https://sequana.readthedocs.io>`_ developers seeking to integrate Snakemake pipelines into the Sequana project. Please refer below for more information. Additionally, note that as a developer, you can generate the reference documentation using Sphinx::

    make html
    browse build/html/index.html


❓ What is sequana_pipetools ?
======================================

**sequana_pipetools** is a collection of tools designed to facilitate the management of `Sequana <https://sequana.readthedocs.io>`_ pipelines, which includes next-generation sequencing (NGS) pipelines like RNA-seq, variant calling, ChIP-seq, and others.

The aim of this package is to streamline the deployment of `Sequana pipelines <https://sequana.readthedocs.io>`_ by
creating a pure Python library that includes commonly used tools for various pipelines.

Previously, the Sequana framework incorporated all bioinformatics, Snakemake rules,
pipelines, and pipeline management tools into a single library (Sequana) as illustrated
in **Fig 1** below.

.. figure:: https://raw.githubusercontent.com/sequana/sequana_pipetools/main/doc/veryold.png

    **Figure 1** Old Sequana framework will all pipelines and Sequana library in the same
    place including pipetools (this library).

Despite maintaining an 80% test coverage, whenever changes were introduced to the Sequana library, a comprehensive examination of the entire library was imperative. The complexity escalated further when incorporating new pipelines or dependencies. To address this challenge, we initially designed all pipelines to operate independently, as depicted in **Fig. 2**. This approach allowed modifications to pipelines without necessitating updates to Sequana and vice versa, resulting in a significant improvement.


.. figure:: https://raw.githubusercontent.com/sequana/sequana_pipetools/main/doc/old.png

    **Figure 2** v0.8 of Sequana moved the Snakemake pipelines in independent
    repositories. A `cookie cutter <https://github.com/sequana/sequana_pipeline_template>`_
    ease the creation of such pipelines


Nevertheless, certain tools, including those utilized for user interface and input data sanity checks, were essential for all pipelines, as illustrated by the pipetools box in the figure. With the continuous addition of new pipelines each month, our goal was to enhance the modularity of both the pipelines and Sequana. As a result, we developed a pure Python library named sequana_pipetools, depicted in **Fig. 3**, to further empower the autonomy of the pipelines.



.. figure:: https://raw.githubusercontent.com/sequana/sequana_pipetools/main/doc/new.png

    **Figure 3** New Sequana framework. The new Sequana framework comprises the core library
    and bioinformatics tools, which are now separate from the pipelines. Moreover, the
    sequana_pipetools library provides essential tools for the creation and management
    of all pipelines, including a shared parser for options

As a final step, we separated the rules originally available in Sequana to create an independent package featuring a collection of Snakemake wrappers. These wrappers can be accessed at https://github.com/sequana/sequana-wrappers and offer the added benefit of being rigorously tested through continuous integration.

.. figure:: https://raw.githubusercontent.com/sequana/sequana_pipetools/main/doc/wrappers.png

    **Figure 3** New Sequana framework 2021. The library itself with the core, the
    bioinformatics tools is now fully independent of the pipelines.



Quick tour of the standalone
============================

The **sequana_pipetools** package provide a standalone called **sequana_pipetools**. Here is a snapshot of the user interface:

.. figure:: https://raw.githubusercontent.com/sequana/sequana_pipetools/main/doc/UI.png

There are several applications. The first one is for Linux users under
bash to obtain completion of a sequana pipeline command line arguments::

    sequana_pipetools --completion fastqc

The second is used to introspect slurm files to get a summary of the SLURM log
files::

    sequana_pipetools --slurm-diag

It searches for files with pattern **slurm** in the current directory and slurm files in the ./logs directory.
This is used within th pipeline but can be used manually as well and is useful to get a quick summary of common errors found in slurm files.

The following command provides statistics about Sequana pipelines installed on your system (number of rules, wrappers
used)::

    sequana_pipetools --stats

And for developpers, a quick creation of schema file given a config file (experimental, developers would still need to edit the schema but it does 90% of the job)::

    sequana_pipetools --config-to-schema config.yaml > schema.yaml

You can also convert the dot file into a nice PNG file using::

    sequana_pipetools --dot2png dag.dot


For Sequana developers
======================

The library is intended to help Sequana developers to design their pipelines.
See the `Sequana organization repository for examples <https://github.com/sequana>`_.
In addition to the standalone shown above, **sequana_pipetools** main goal is to provide utilities to help Sequana developers.

First, let us create a pipeline

Initiate a project (Sequana pipeline) with cookiecutter
-------------------------------------------------------

You can start a Sequana pipeline skeleton as follows::

    sequana_pipetools --init-new-pipeline

and then follow the instructions. You will be asked some questions such as the name of your pipeline (eg. variant), a description, keywords and the *project_slug* (just press enter).

Update the main script
-----------------------

Go to sequana_pipelines/NAME and look at the main.py script.

We currently provide a set of Options classes that should be used to
design the API of your pipelines. For example, the
sequana_pipetools.options.SlurmOptions can be used as follows inside a standard
Python module (the last two lines is where the magic happens)::


    import rich_click as click
    from sequana_pipetools.options import *
    from sequana_pipetools import SequanaManager

    NAME = "fastqc"
    help = init_click(NAME, groups={
        "Pipeline Specific": [
            "--method", "--skip-multiqc"],
            }
    )

    @click.command(context_settings=help)
    @include_options_from(ClickSnakemakeOptions, working_directory=NAME)
    @include_options_from(ClickSlurmOptions)
    @include_options_from(ClickInputOptions, add_input_readtag=False)
    @include_options_from(ClickGeneralOptions)
    @click.option("--method", default="fastqc", type=click.Choice(["fastqc", "falco"]), help="your msg")
    def main(**options):

        # the real stuff is here
        manager = SequanaManager(options, NAME)
        manager.setup()

        # just two aliases
        options = manager.options
        cfg = manager.config.config


        # fills input_data, input_directory, input_readtag
        manager.fill_data_options()

        # fill specific options.
        # create a function for a given option (here --method)
        def fill_method():
            # any extra sanity checks
            cfg["method"] = options["method"]

        if options["from-project"]:
            # in --from-project, we fill the method is --method is provided only (since already pre-filled)
            if "--method" in sys.argv
                fill_method()
        else:
            # in normal, we always want to fill the user-provided option
            fill_method()

        # finalise the command and save it; copy the snakemake. update the config
        # file and save it.
        manager.teardown()

    if __name__ == "__main__":
        main()



Developers should look at e.g. module sequana_pipetools.options
for the API reference and one of the official sequana pipeline (e.g.,
https://github.com/sequana/sequana_variant_calling) to get help from examples.

The Options classes provided can be used and combined to design pipelines.


How to use sequana pipetools within your Pipeline
--------------------------------------------------

For FastQ files (paired ot not), The config file should look like::

    sequana_wrappers: "v0.15.1"

    input_directory: "."
    input_readtag: "_R[12]_"
    input_pattern: "*fastq.gz"


    apptainers:
        fastqc: "https://zenodo.org/record/7923780/files/fastqc_0.12.1.img"

    section1:
        key1: value1
        key2: value2

And your pipeline could make use of this as follows::

    configfile: "config.yaml"

    from sequana_pipetools import PipelineManager
    manager = PipelineManager("fastqc", config)

    # you can then figure out wheter it is paired or not:
    manager.paired

    # get the wrapper version to be used within a rule:
    manager.wrappers

    # the raw data (with a wild card) for the first rule
    manager.getrawdata()

    # add a Makefile to clean things at the end
    manager.teardown()


Setting up and Running Sequana pipelines
-----------------------------------------


When you execute a sequana pipeline, e.g.::

    sequana_fastqc --input-directory data

a working directory is created (with the name of the pipeline; here fastqc). Moreover, the working directory
contains a shell script that will hide the snakemake command. This snakemake command with make use
of the sequana wrappers and will use the official sequana github repository by default
(https://github.com/sequana/sequana-wrappers). This may be overwritten. For instance, you may use a local clone. To do
so, you will need to create an environment variable::

    export SEQUANA_WRAPPERS="git+file:///home/user/github/sequana-wrappers"

If you decide to use singularity/apptainer, one common error on a cluster is that non-standard paths are not found. You can bind them using the -B option but a more general set up is to create this environment variable::

    export SINGULARITY_BINDPATH="/path_to_bind"

for Apptainer setup ::

    export APPTAINER_BINDPATH="/path_to_bind"



What is Sequana ?
=================

**Sequana** is a versatile tool that provides

#. A Python library dedicated to NGS analysis (e.g., tools to visualise standard NGS formats).
#. A set of Pipelines dedicated to NGS in the form of Snakefiles
   (Makefile-like with Python syntax based on snakemake framework) with more
   common wrappers.
#. Standalone applications such as sequana_coverage and sequana_taxonomy.

See the `sequana home page <https://sequana.readthedocs.io>`_ for details.


To join the project, please let us know on `github <https://github.com/sequana/sequana/issues/306>`_.



Changelog :memo:
================

========= ======================================================================
Version   Description
========= ======================================================================
1.2.2     * download sequana-wrapper-lite and automatically fill config file.
1.2.1     * create apptainer directory if it does not exist
          * --use-apptainer set to True internally is --apptainer-prefix is used
          * do not store conda env anymore since we are using containers
1.2.0     * update to be compatible with poetry 2.0
          * print container size when initiating a pipeline
1.1.1     * symlink creation on apptainers skipped if permission error (file
            is probably already present and created by another users e.g.
            the admin system)
          * add --init-new-pipeline argument in sequana_pipetools standalone
1.1.0     * add exclude_pattern in input data section
1.0.6     * add py3.12, slight updates wrt slurm
1.0.5     * introspect slurm files to extract stats
1.0.4     * add utility function to download and untar a tar.gz file
1.0.3     * add levenshtein function. some typo corrections.
1.0.2     * add the dot2png command. pin docutils <0.21 due to pip error
1.0.1     * hot fix in the profile creation (regression)
1.0.0     * Stable release
0.17.3    * remove useless code and fix a requirement
0.17.2    * simpler logging
0.17.1    * remove the --use-singulariry (replaced by --use-apptainer in
            previous release)
          * slight updates on logging and slight update on slurm module
0.17.0    * Remove deprecated options and deprecated functions. More tests.
0.16.9    * Fix slurm sys exit (replaced by print)
          * upadte doc
          * more tests
0.16.8    * stats command add the number of rules per pipeline
          * better slurm parsing using profile tree directory (slurm in logs/)
0.16.7    * add missing --trimming-quality option in list of TrimmingOption
          * set default to cutadatp if no fastp available
          * better UI for the completion script.
0.16.6    * Set default value for the option trimming to 20
          * Fix issue https://github.com/sequana/sequana_pipetools/issues/85
0.16.5    * merge completion standalone into main sequana_pipetools application
          * add application to create schema given a config file
          * add application to get basic stats about the pipelines
          * add precommit and applied black/isort on all files
          * remove some useless code
          * update completion to use click instead of argparse
          * Rename Module into Pipeline (remove rules so Module are only made
            of pipelines hence the renaming)
0.16.4    * fix Trimming options (click) for the quality option
0.16.3    * add class to handle multiplex entry for click.option (useful for
            multitax multiple databases)
0.16.2    * remove useless function get_pipeline_location, get_package_location
            guess_scheduler from sequana_manager (not used)
          * store sequana version correctly in info.txt Fixing #89
          * sort click options alphabetically
          * --from-project not funtcional (example in multitax pipeline)
          * Click checks that input-directoyr is a directory indeed
0.16.1    * Fix/rename error_report into onerror to be included in the Snakemake
            onerror section. added *slurm* in slurm output log file in the
            profile
0.16.0    * scripts now use click instead of argparse
          * All Options classes have now an equivalent using click.
            For example GeneralOptions has a class ClickGeneralOptions.
            The GeneralOptions is kept for now for back compatibility
          * --run-mode removed and replaced by --profile options. Profiles are
            used and stored withub .sequana/profiles
          * Remove --slurm-cores-per-job redundant with resources from snakemake
          * Way a main.py is coded fully refactored and simplified as described
            in the README
          * cluster_config are now deprecated in favor of profile
          * sequana_slurm_status removed. Use manager.error_report in pipelines
            instead
0.15.0    * remove useless code (readme, description) related to old rules
          * requirements.txt renamed in tools.txt to store the required tools to
            run a pipeline.
          * remove copy_requirements, not used in any pipelines (replaced by code
            in main.py of the pipelines)
          * a utility function called getmetadata that returns dictionary
            with name, version, wrappers version)
0.14.X    * Module now returns the list of requirements. SequanaManager
            creates a txt file with all standalones from the requirements.
0.13.0    * switch to pyproject and fixes #64
0.12.X    * automatically populater *wrappers* in PipelineManager based on the
            config entry *sequana_wrappers*.
          * Fix the singularity arguments by (i) adding -e and (ii) bind the
            /home. Indeed, snakemake sets --home to the current directory.
            Somehow the /home is lost. Removed deprecated function
          * factorise hash function to have url2hash easily accessible
          * remove harcoded bind path for apptainer. Uses env variable instead
0.11.X    * fix regression, add codacy badge, applied black, remove
            init_pipeline deprecated function.
0.10.X    * Fixes https://github.com/sequana/sequana_pipetools/issues/49
            that properly sets the apptainer prefix in defualt mode
0.9.X     * replaced singularity word by apptainer (--use-aptainer instead of
            --use-singularity)
          * add config2schema utility function for developers
          * Ability to download automatically singularity images (as URLs) if
            set in the  pipelines (container field). add the --use-singularity
            option in all pipelines (and --singualrity-prefix)
0.9.0     * **MAJOR update/Aug 2022**
          * new mechanism to handle  profile for Snakemake that will replace the
            cluster_config.yaml files
          * Major cleanup of PipelineManager (PipelineManagerGeneric was
            removed). The way input files are handled was also cleanup.
            Fixes https://github.com/sequana/sequana_pipetools/issues/37
            and also files starting with common prefixes
0.8.X     * Better schema validation. switch from distutils to packaging
0.7.X     * simplify the setup() method in pipeline manager
            can set a SEQUANA_WRAPPERS env variable to use local wrappers
            add schema pipeline manager directory & fix attrdict error with yaml
          * Set the --wrapper-prefix to point to the  sequana-wrappers github
0.6.X     * Fix SequanaConfig file to include wrapper
            and take new snakemake syntax into account. update schema handling
          * Move all modules related to pipelines from sequana into
            sequana_pipetools
0.5.X     * feature removed in sequana to deal with adapter removal and
            changes updated in the package (removed the *design* option
            from the cutadapt rules and needed); add TrimmingOptions.
0.4.X     * add FeatureCounts options and slurm status utility
0.4.0     * stable version
0.3.X     * first stable release
0.2.X     * completion can now handle multiple directories/files properly
            better doc and more tests; add --from-project option to import
            existing config file; remove --paired-data option; add content
            from sequana.pipeline_common
0.1.X     * software creation
========= ======================================================================


:left_speech_bubble: Contacts <a name="contacts"></a>
:question: Feel free to [open an issue](https://github.com/sequana/sequana_pipetools/issues)
