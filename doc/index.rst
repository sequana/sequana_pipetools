Sequana_pipetools documentation 
########################################



.. include:: ../README.rst

What is sequana_pipetools ?
============================

**sequana_pipetools** is a set of tools to help us in managing the **Sequana** pipelines.

This has the advantage of being pure Python library without the needs to update
**Sequana** itself.


**Sequana** is a versatile tool that provides 

#. A Python library dedicated to NGS analysis (e.g., tools to visualise standard NGS formats).
#. A set of pipelines dedicated to NGS in the form of Snakefiles
   (Makefile-like with Python syntax based on snakemake framework) with more
   than 80 re-usable rules.
#. Standalone applications.

See the home page for details.


To join the project, please let us know on `github <https://github.com/sequana/sequana/issues/306>`_.

Installation
============

from pypi website::

    pip install sequana_pipetools

No dependencies for this package except Python itself. Although, when using it,
you will need to install the relevant Sequana pipelines that you wish to use. 

This package is for `Sequana <https://sequana.readthedocs.io>`_ developers. 

Usage
======

There is currently only one tool to be used as follows::

    sequana_completion --pipeline fastqc


.. toctree::

    references


Changelog
=========

========= ====================================================================
Version   Description
========= ====================================================================
0.1.0     creation of the package
========= ====================================================================

