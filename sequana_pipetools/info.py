# -* coding: utf-8 -*-
#
#  This file is part of Sequana software
#
#  Copyright (c) 2016 - Sequana Development Team
#
#  File author(s):
#      Thomas Cokelaer <thomas.cokelaer@pasteur.fr>
#      Dimitri Desvillechabrol <dimitri.desvillechabrol@pasteur.fr>,
#          <d.desvillechabrol@gmail.com>
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
""".. rubric:: misc utilities"""

from sequana_pipetools.misc import Colors


__all__ = ["sequana_epilog"]


sequana_epilog = Colors().purple("""If you use or like the Sequana project,
please consider citing us (visit sequana.readthedocs.io for details) or use this
citation:

Cokelaer et al, (2017), ‘Sequana’: a Set of Snakemake NGS pipelines, Journal of
Open Source Software, 2(16), 352, JOSS DOI doi:10.21105/joss.00352


""")

sequana_prolog = """Welcome to Sequana project (https://sequana.readthedocs.io)

This script prepares the pipeline sequana_{name}. It stores the pipeline and its 
configuration file in the requested working directory ({name} by default). 
Please check out the documentation carefully. In case of issues, please report
on https://github.com/sequana/sequana/issues or https://github.com/sequana/{name}/issues

Pipelines can be run locally or on a SLURM cluster. If not slurm commands are
found, te pipeline is in mode 'local', otherwise in mode 'slurm'.

A working directory called {name} is created with a {name}.sh script to be executed.
"""



