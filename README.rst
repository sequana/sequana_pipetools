

.. image:: https://badge.fury.io/py/sequana-pipetools.svg
    :target: https://pypi.python.org/pypi/sequana_pipetools

.. image:: https://github.com/sequana/sequana_pipetools/actions/workflows/main.yml/badge.svg?branch=master
    :target: https://github.com/sequana/sequana_pipetools/actions/workflows/main.yml
    
.. image:: https://coveralls.io/repos/github/sequana/sequana_pipetools/badge.svg?branch=master
    :target: https://coveralls.io/github/sequana/sequana_pipetools?branch=master 

.. image:: http://joss.theoj.org/papers/10.21105/joss.00352/status.svg
   :target: http://joss.theoj.org/papers/10.21105/joss.00352
   :alt: JOSS (journal of open source software) DOI

:Overview: A set of tools to help building or using sequana pipelines
:Status: Production
:Issues: Please fill a report on `github <https://github.com/sequana/sequana/issues>`__
:Python version: Python 3.7, 3.8, 3.9
:Citation: Cokelaer et al, (2017), ‘Sequana’: a Set of Snakemake NGS pipelines, Journal of Open Source Software, 2(16), 352,  `JOSS DOI doi:10.21105/joss.00352 <http://www.doi2bib.org/bib/10.21105%2Fjoss.00352>`_


What is sequana_pipetools ?
============================

**sequana_pipetools** is a set of tools to help us managing the `Sequana <https://sequana.readthedocs.io>`_ pipelines (NGS pipelines such as RNA-seq, Variant, ChIP-seq, etc).

The goal of this package is to make the deployment of `Sequana pipelines <https://sequana.readthedocs.io>`_ easier
by moving some of the common tools used by the different pipelines in a pure
Python library. 


The Sequana framework used to have all bioinformatics, snakemake rules,
pipelines, tools to manage pipelines in a single library (Sequana) as described
in **Fig 1** here below.

.. figure:: https://raw.githubusercontent.com/sequana/sequana_pipetools/master/doc/veryold.png
    :scale: 40%

    **Figure 1** Old Sequana framework will all pipelines and Sequana library in the same
    place including pipetools (this library).

Each time we changed anything, the entire library needed to be checked carefully
(even though we had 80% test coverage). Each time a pipeline was added, new
dependencies woule be needed, and so on. So, we first decided to make all
pipelines independent as shown in **Fig 2**:

.. figure:: https://raw.githubusercontent.com/sequana/sequana_pipetools/master/doc/old.png
    :scale: 40%
    
    **Figure 2** v0.8 of Sequana moved the Snakemake pipelines in indepdendent
    repositories. A `cookie cutter <https://github.com/sequana/sequana_pipeline_template>`_ 
    ease the creation of scuh pipelines

That way, we could change a pipeline without the need to update Sequana, and
vice-versa. This was already a great jump ahead. Yet, some tools reprensented
here by the *pipetools* box were required by all pipelines. This was mostly for
providing user interface, sanity check of input data, etc. This was moving fast
with new pipelines added every month. To make the pipelines and Sequana more
modular, we decided to create a pure Python library that would make the
pipelines even more independent as shown in **Fig3**. We called it
**sequana_pipetools**.


.. figure:: https://raw.githubusercontent.com/sequana/sequana_pipetools/master/doc/new.png
    :scale: 40%

    **Figure 3** New Sequana framework. The library itself with the core, the
    bioinformatics tools is now independent of the pipelines. Besides, the
    pipetools library provide common tools to all pipelines to help in their
    creation/management. For instance, common parser for options.




Installation
============

from pypi website::

    pip install sequana_pipetools

No dependencies for this package except Python itself. In practice, this package
has no interest if not used with a Sequana pipeline. So, when using it,
you will need to install the relevant Sequana pipelines that you wish to use.

This package is for `Sequana <https://sequana.readthedocs.io>`_ developers. 
To get more help, go to the doc directory and build the local sphinx directory using::

    make html
    browse build/html/index.html

Quick tour
==========

There are currently two standalone tools. The first one is for Linux users under
bash to obtain completion of a sequana pipeline command line arguments::

    sequana_completion --name fastqc

The second is used to introspect slurm files to get a summary of the SLURM log
files::

    sequana_slurm_status --directory .

Will print a short summary report with common errors (if any).


The library is intended to help Sequana developers to design their pipelines.
See the `Sequana organization repository for examples <https://github.com/sequana>`_.

In addition to those standalones, sequana_pipetools goal is to provide utilities to help Sequana developers. 
We currently provide a set of Options classes that should be used to
design the API of your pipelines. For example, the
sequana_pipetools.options.SlurmOptions can be used as follows inside a standard
Python module (the last two lines is where the magic happens)::

    import argparse
    from sequana_pipetools.options import *
    from sequana_pipetools.misc import Colors
    from sequana_pipetools.info import sequana_epilog, sequana_prolog

    col = Colors()
    NAME = "fastqc"

    class Options(argparse.ArgumentParser):
        def __init__(self, prog=NAME, epilog=None):
            usage = col.purple(sequana_prolog.format(**{"name": NAME}))
            super(Options, self).__init__(usage=usage, prog=prog, description="",
                epilog=epilog,
                formatter_class=argparse.ArgumentDefaultsHelpFormatter
            )
            # add a new group of options to the parser
            so = SlurmOptions()
            so.add_options(self)


Developers should look at e.g. module sequana_pipetools.options
for the API reference and one of the official sequana pipeline (e.g.,
https://github.com/sequana/sequana_variant_calling) to get help from examples.


The Options classes provided can be used and combined to design pipelines. The
code from sequana_pipetools is used within our template to automatically create
pipeline tree structure using a cookie cutter. This cookie cutter is available  
in https://github.com/sequana/sequana_pipeline_template and as a
standalone in Sequana itself (sequana_init_pipeline).

What is Sequana ?
=================

**Sequana** is a versatile tool that provides 

#. A Python library dedicated to NGS analysis (e.g., tools to visualise standard NGS formats).
#. A set of Pipelines dedicated to NGS in the form of Snakefiles
   (Makefile-like with Python syntax based on snakemake framework) with more
   than 80 re-usable rules.
#. Standalone applications.

See the `sequana home page <https://sequana.readthedocs.io>`_ for details.


To join the project, please let us know on `github <https://github.com/sequana/sequana/issues/306>`_.



Changelog
=========

========= ====================================================================
Version   Description
========= ====================================================================
0.7.1     * Fix the --from-project option
0.7.0     * Set the --wrapper-prefix to point to the  sequana-wrappers github
0.6.3     * Fix SequanaConfig file
0.6.2     * Fix script creation to include wrapper and take new snakemake 
            syntax into account
0.6.1     * update schema handling
0.6.0     * Move all modules related to pipelines rom sequana into 
            sequana_pipetools; This release should now be the entry point for 
            all Sequana pipelines (no need to import sequana itself).
0.5.3     * feature removed in sequana to deal with adapter removal and
            changes updated in the package (removed the 'design' option 
            from the cutadapt rules and needed)
          * Improve TrimmingOptions to provide specific list of tools 
            and a default trimming tool
0.5.2     * add TrimmingOptions class intended at replacing CutadaptOptions
          * to avoid extra spaces, add '-o nospace' in all completion files
0.5.1     * fix typo
0.5.0     * add new module called error to be added in onerror sections of all
            pipelines. Usual test update. Pin to stable version
0.4.3     * add MANIFEST to include missing requirements.txt
0.4.2     * add FeatureCounts options
0.4.1     * add slurm status utility (sequana_slurm_status)
0.4.0     * stable version
0.3.1     * comment the prin_newest_version, which is too slow
0.3.0     * stable release
0.2.6     * previous new feature led to overhead of a few seconds with --help
            in this version, we include it only when using --version
0.2.5     * include newest_version feature
0.2.4     * completion can now handle multiple directories/files properly 
          * better doc and more tests
0.2.3     * fix completion to avoir 2 scripts to overwrite each other
0.2.2     * add a deprecated warning + before_pipeline function
0.2.1     * add --from-project option to import existing config file
          * remove --paired-data option
0.2.0     add content from sequana.pipeline_common to handle all kind of 
          options in the argparse of all pipelines. This is independent of 
          sequana to speed up the --version and --help calls
0.1.2     add version of the pipeline in the output completion file 
0.1.1     release bug fix
0.1.0     creation of the package
========= ====================================================================
