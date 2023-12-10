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
import pkgutil
import sys

import colorlog
import pkg_resources
from easydev import get_package_location as gpl

from sequana_pipetools.misc import Singleton

logger = colorlog.getLogger(__name__)


class ModuleFinder(metaclass=Singleton):
    """Data structure to hold the :class:`Module` names"""

    def __init__(self):
        """.. rubric:: constructor

        :param list extra_paths:

        .. doctest::

            >>> from sequana import ModuleFinderSingleton
            >>> modnames = ModuleFinderSingleton()
            >>> modnames.isvalid('fastqc')
            True
            >>> modnames.isvalid('dummy')
            False

        """
        # names for each directory
        self._paths = {}
        self._type = {}

        # scan all pipeline from sequana_pipelines namespace
        self._add_pipelines()

    def _add_pipelines(self):
        try:
            import sequana_pipelines
        except ModuleNotFoundError:  # pragma: no cover
            logger.debug("sequana pipelines not installed. Please install a pipeline from github.com/sequana")
            return

        for ff, module_name, _ in pkgutil.iter_modules(sequana_pipelines.__path__):
            self._paths[f"{module_name}"] = ff.path + os.sep + module_name

            logger.debug("Found {} pipeline".format(module_name))

    def _get_names(self):
        return sorted(list(self._paths.keys()))

    names = property(_get_names, doc="list of existing module names")

    def isvalid(self, name):
        """Check that a name is an existing and valid module"""
        if name not in self.names:
            return False
        return True
