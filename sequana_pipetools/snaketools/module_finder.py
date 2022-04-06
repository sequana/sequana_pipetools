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
            >>> modnames.isvalid('dag')
            True
            >>> modnames.isvalid('dummy')
            False

        """
        # names for each directory
        self._paths = {}
        self._type = {}

        # scan the official path for all rules
        self._add_rules()

        # scan all pipeline from sequana_pipelines namespace
        self._add_pipelines()

    def _is_version(self, version, path):
        try:
            # if we can convert the name into an integer, we have an integer for
            # a rule name, which is not possible
            int(version)
            logger.error(f"A rule name cannot be a number. Found rule named {version}")
            sys.exit(1)
        except ValueError:
            pass

        if "." in version:
            if version.count(".") == 1:
                x, y = version.split(".")
                int(x)
                int(y)
            else:
                logger.error(
                    "A module version can only contain a single"
                    ". character, which is used for setting module's "
                    "version in the form x.y"
                )
                sys.exit(1)
            return True
        else:
            return False

    def _add_rules(self):
        # FIXME remove it when rules are deprecated
        sepjoin = os.sep.join
        try:
            fullpath = sepjoin([gpl("sequana"), "sequana", "rules"])
        except pkg_resources.DistributionNotFound:
            return
        fullpaths = self._iglob(fullpath)

        for this in fullpaths:
            whatever, module_name, filename = this.rsplit(os.sep, 2)
            if module_name in self._paths.keys():
                logger.warning("Found duplicated name %s from %s" % (module_name, this) + "Overwrites previous rule ")

            if self._is_version(module_name, this):
                # the module name is the name before the version + the version
                module_name = filename.replace(".rules", "") + "/" + module_name
                name, version = module_name.split("/")
                self._paths[module_name] = whatever + os.sep + version
            else:
                self._paths[module_name] = whatever + os.sep + module_name

    def _add_pipelines(self):
        try:
            import sequana_pipelines
        except ModuleNotFoundError:
            logger.warning("sequana pipelines not installed. Please install a pipeline from github.com/sequana")
            return

        import pkgutil

        for ff, module_name, _ in pkgutil.iter_modules(sequana_pipelines.__path__):
            self._paths[f"pipeline:{module_name}"] = ff.path + os.sep + module_name

            logger.debug("Found {} pipeline".format(module_name))

    def _iglob(self, path, extension="rules"):
        from glob import iglob

        matches = tuple(iglob("%s/**/*.%s" % (path, extension), recursive=True))
        return matches

    def _get_names(self):
        return sorted(list(self._paths.keys()))

    names = property(_get_names, doc="list of existing module names")

    def isvalid(self, name):
        """Check that a name is an existing and valid module"""
        if name not in self.names:
            return False
        return True
