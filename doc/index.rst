Sequana_pipetools documentation
###############################

|version|, |today|


.. raw:: html

    <div style="width:80%"><p>

    <a href="https://pypi.python.org/pypi/sequana_pipetools">
    <img src="https://badge.fury.io/py/sequana_pipetools.svg"></a>

    <a href="https://travis-ci.org/sequana/sequana_pipetools">
    <img src="https://travis-ci.org/sequana/sequana_pipetools.svg?branch=master"></a>

    <a href="https://coveralls.io/github/sequana/sequana_pipetools?branch=master">
    <img src="https://coveralls.io/repos/github/sequana/sequana_pipetools/badge.svg?branch=master"></a>

    <a href="http://joss.theoj.org/papers/10.21105/joss.00352">
    <img src="http://joss.theoj.org/papers/10.21105/joss.00352/status.svg"></a>

    </p>
    </div>


:Python version: Python 3.6, 3.7.3; most modules are Python2.7 compatible.
:Source: See  `source <https://github.com/sequana/sequana/>`__.
:Issues: Please fill a report on `github <https://github.com/sequana/sequana/issues>`__
:How to cite: For Sequana in general including the pipelines, please use

    Cokelaer et al, (2017), 'Sequana': a Set of Snakemake NGS pipelines, Journal of
    Open Source Software, 2(16), 352, `JOSS DOI doi:10.21105/joss.00352 <http://www.doi2bib.org/bib/10.21105%2Fjoss.00352>`_

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

Changelog
=========

========= ====================================================================
Version   Description
========= ====================================================================
0.1.0     creation of the package
========= ====================================================================

