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
import shutil

import colorlog
import easydev
import pkg_resources

from .module_finder import ModuleFinder

logger = colorlog.getLogger(__name__)


class Pipeline:
    """Data structure that holds metadata about a **Sequana Pipeline**

    So, a **Pipeline** in sequana's parlance is a directory that contains:

        - A **snakemake** file named after the directory with the extension
          **.rules**
        - A **README.rst** file in restructured text format
        - An optional config file in YAML format named config.yaml.
          Although json format is possible, we use YAML throughout
          **sequana** for consistency. Rules do not have any but pipelines
          do. So if a pipeline does not provide a config.yaml, the one found
          in ./sequana/sequana/pipelines will be used.
        - a **tools.txt** with list of expected standalones required by the pipeline
          (non-python tools).

    The :class:`Pipeline` will ease the retrieval of information linked to a
    rule or pipeline. For instance if a pipeline has a config file, its path
    can be retrived easily::

        m = Pipeline("quality_control")
        m.config

    """

    def __init__(self, name):
        """.. rubric:: Constructor

        :param str name: the name of an available module.

        """
        self._mf = ModuleFinder()
        self._mf.isvalid(name)

        if name not in self._mf.names:
            raise ValueError(
                """Sequana error: unknown rule or pipeline '{}'.
Check the source code at:

    https://github.com/sequana/sequana/tree/develop/sequana/pipelines and
    https://github.com/sequana/sequana/tree/develop/sequana/rules

or open a Python shell and type::

    from sequana_pipetools.snaketools.module import modules
    modules.keys()""".format(
                    name
                )
            )
        else:
            self._path = self._mf._paths[name]

        self._name = name

        self._snakefile = None
        self._requirements = None
        self._requirements_names = None

    def _get_file(self, name):
        filename = os.sep.join((self._path, name))
        if os.path.exists(filename):
            return filename

    def __repr__(self):
        _str = "Name: %s\n" % self._name
        _str += "Path: %s\n" % self.path
        _str += "Config: %s\n" % self.config
        _str += "Schema for config file: %s\n" % self.schema_config
        _str += "Multiqc config file: %s\n" % self.multiqc_config
        _str += "tools file: %s\n" % self.requirements
        _str += "version: %s\n" % self.version
        return _str

    def __str__(self):
        txt = "Rule **" + self.name
        return txt

    def _get_version(self):

        ver = pkg_resources.require(f"sequana_{self.name}")[0].version
        return ver

    version = property(_get_version, doc="Get version")

    def _get_path(self):
        return self._path

    path = property(_get_path, doc="full path to the module directory")

    def _get_config(self):
        # list of module config file and sequana default config file
        default_filenames = ("config.yaml", "config.yml", "../config.yaml", "../config.yml")
        for default_filename in default_filenames:
            filename = self._get_file(default_filename)
            if filename:
                return filename
        return filename

    config = property(_get_config, doc="full path to the config file of the module")

    def _get_schema_config(self):
        # The default config file for that module
        default_filenames = ("schema.yaml", "schema.yml", "../schema.yaml", "../schema.yml")
        for default_filename in default_filenames:
            filename = self._get_file(default_filename)
            if filename:
                return filename
        return filename

    schema_config = property(_get_schema_config, doc="full path to the schema config file of the module")

    def _get_multiqc_config(self):
        filename = self._get_file("multiqc_config.yaml")
        return filename

    multiqc_config = property(_get_multiqc_config, doc="full path to the multiqc config file of the module")

    def _get_logo(self):
        filename = self._get_file("logo.png")
        return filename

    logo = property(_get_logo, doc="full path to the logo of the module")

    def _get_snakefile(self):
        if self._snakefile:
            return self._snakefile

        # tuple of all possible snakefiles
        possible_snakefiles = (
            "Snakefile",
            f"Snakefile.{self.name}",
            f"{self.name}.rules",
            f"{self.name}.smk",
            f"{self.name.replace('pipeline:', '')}.rules",
            f"{self.name.replace('pipeline:', '')}.smk",
        )

        # find the good one
        for snakefile in possible_snakefiles:
            self._snakefile = self._get_file(snakefile)
            if self._snakefile:
                return self._snakefile

        # find with version
        if self.version:
            name, _ = self.name.split("/")
            name = os.sep.join((self._path, f"{name}.rules"))
            self._snakefile = name
        return self._snakefile

    snakefile = property(_get_snakefile, doc="full path to the Snakefile file of the module")

    def _get_rules(self):
        return self._get_file("rules")

    rules = property(_get_rules, "full path to the pipeline rules")

    def _get_name(self):
        return self._name

    name = property(_get_name, doc="name of the module")

    def _get_requirements(self):
        if self._requirements is not None:
            return self._requirements
        if self._get_file("tools.txt"):
            self._requirements = self._get_file("tools.txt")
            return self._requirements
        if self._get_file("requirements.txt"):  # pragma: no cover
            logger.warning("Warning for developer. The requirements.txt should be renamed into tools.txt")
            self._requirements = self._get_file("requirements.txt")
            return self._requirements

    requirements = property(_get_requirements, doc="requirements filename")

    def _get_requirements_names(self):
        if self._requirements_names is not None:
            return self._requirements_names

        # FIXME: could probably remove to enforce existence of the file
        if self.requirements is None:  # pragma: no cover
            self._requirements_names = []
            return self._requirements_names

        if self.requirements:
            with open(self.requirements, "r") as fh:
                data = fh.read()
                datalist = [this.strip() for this in data.split("\n") if len(this.strip()) > 0]
                reqlist = []
                for this in datalist:
                    if this.startswith("-"):
                        req = this.split("-", 1)[1].strip()
                        reqlist.append(req)
                    else:
                        req = this.strip()
                        reqlist.append(req)
            self._requirements_names = reqlist
            return self._requirements_names

    requirements_names = property(_get_requirements_names, doc="list of requirements names")

    def is_executable(self):
        """Is the module executable

        A Pipeline Module should have a requirements.txt file that is
        introspected to check if all executables are available;

        :return: a tuple. First element is a boolean to tell if it executable.
            Second element is the list of missing executables.
        """
        if self.requirements is None:
            return True, []

        executable = True
        missing = []

        # reads the file and interpret it to figure out the
        # executables/packages and pipelines required
        pipelines = []

        # Check the pipelines independently
        for pipeline in pipelines:
            Pipeline(pipeline).check()

        for req in self.requirements_names:
            # It is either a Python package or an executable
            if req.startswith("#"):
                continue
            try:
                shutil.which(f"{req}")
                logger.debug(f"Found {req} executable")
            except Exception:  # pragma: no cover
                # is this a Python code ?
                if len(easydev.get_dependencies(req)) == 0:
                    executable = False
                    missing.append(req)
                else:
                    logger.info(f"{req} python package")
        return executable, missing

    def check(self, mode="warning"):
        executable, missing = self.is_executable()

        if executable is False:  # pragma: no cover
            # _ = self.is_executable()
            missing = " ".join(missing)
            txt = f"""Some executable or Python packages are not available: {missing}
Some functionalities may not work. Consider adding them with conda or set the --use-apptainer options.

            """

            if mode == "warning":
                logger.critical(txt)
            elif mode == "error":  # pragma: no cover
                txt += "you may want to use \n conda install {missing};"
                for this in missing:
                    txt += "- %s\n" % this
                raise ValueError(txt)

    def md5(self):
        """return md5 of snakefile and its default configuration file

        ::

            >>> from sequana import snaketools as sm
            >>> m = sm.Pipeline("variant_calling")
            >>> m.md5()
            {'config': 'e23b26a2ff45fa9ddb36c40670a8a00e',
             'snakefile': '7d3917743a6b123d9861ddbbb5f3baef'}

        """
        data = {}
        data["snakefile"] = easydev.md5(self.snakefile)
        data["config"] = easydev.md5(self.config)
        return data


def _get_modules_snakefiles():
    modules = ModuleFinder()
    for name in modules.names:
        module = Pipeline(name)
        filename = module.snakefile
        if filename:
            yield name, filename


# dictionary with module names as keys and fullpath to the Snakefile as values
modules = {name: filename for name, filename in _get_modules_snakefiles()}

# list of pipeline names found in the list of modules
pipeline_names = [m for m in modules]
