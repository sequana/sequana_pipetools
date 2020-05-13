:Overview: A set of tools to help building or using sequana pipelines
:Status: Production
:Citation: Cokelaer et al, (2017), ‘Sequana’: a Set of Snakemake NGS pipelines, Journal of Open Source Software, 2(16), 352, JOSS DOI doi:10.21105/joss.00352

.. image:: https://badge.fury.io/py/sequana-pipetools.svg
    :target: https://pypi.python.org/pypi/sequana_pipetools

.. image:: https://travis-ci.org/sequana/sequana_pipetools.svg?branch=master
    :target: https://travis-ci.org/sequana/sequana_pipetools

.. image:: https://coveralls.io/repos/github/sequana/sequana_pipetools/badge.svg?branch=master
    :target: https://coveralls.io/github/sequana/sequana_pipetools?branch=master 

.. image:: http://joss.theoj.org/papers/10.21105/joss.00352/status.svg
   :target: http://joss.theoj.org/papers/10.21105/joss.00352
   :alt: JOSS (journal of open source software) DOI



What is sequana_pipetools ?
============================

**sequana_pipetools** is a set of tools to help us in managing the **Sequana** pipelines.

This has the advantage of being pure Python library without the needs to update
**Sequana** itself.


**Sequana** is a versatile tool that provides 

#. A Python library dedicated to NGS analysis (e.g., tools to visualise standard NGS formats).
#. A set of Pipelines dedicated to NGS in the form of Snakefiles
   (Makefile-like with Python syntax based on snakemake framework) with more
   than 80 re-usable rules.
#. Standalone applications.

See the `sequana home page <https://sequana.readthedocs.io>`_ for details.


To join the project, please let us know on `github <https://github.com/sequana/sequana/issues/306>`_.

Installation
============

from pypi website::

    pip install sequana_pipetools

No dependencies for this package except Python itself. Although, when using it,
you will need to install the relevant Sequana pipelines that you wish to use. 

This package is for `Sequana <https://sequana.readthedocs.io>`_ developers. To get more help, go to the doc
directory and build the local sphinx directory using::

    make html
    browse build/html/index.html

Usage
======

There is currently only one tool to be used as follows::

    sequana_completion --pipeline fastqc

The library is intended to help Sequana developers to design their pipelines. 
See the `Sequana orgnization repository for examples <https://github.com/sequana>`_.



Changelog
=========

========= ====================================================================
Version   Description
========= ====================================================================
0.2.1     * add --from-project option to import existing config file
          * remove --paired-data option
0.2.0     add content from sequana.pipeline_common to handle all kind of 
          options in the argparse of all pipelines. This is independent of 
          sequana to speed up the --version and --help calls
0.1.2     add version of the pipeline in the output completion file 
0.1.1     release bug fix
0.1.0     creation of the package
========= ====================================================================
