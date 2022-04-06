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
import glob
import os

import colorlog
import easydev

from .module_finder import ModuleFinder

logger = colorlog.getLogger(__name__)


class Module:
    """Data structure that holds metadata about a **Module**

    In Sequana, we provide rules and pipelines to be used with snakemake.
    Snakemake rules look like::

        rule <name>:
            :input: file1
            :output: file2
            :shell: "cp file1 file2"

    A pipeline may look like::

        include: "path_to_rule1"
        include: "path_to_rule2"
        rule all:
            input: FINAL_FILES

    Note that the pipeline includes rules by providing the path to them.

    All rules can be stored in a single directory. Similarly for pipelines.
    We decided not to use that convention. Instead, we bundle rules (and
    pipelines) in their own directories so that other files can be stored
    with them. We also consider that

        #. if the **Snakefile** includes other **Snakefile** then
           it is **Pipeline**.
        #. Otherwise it is a simple **Rule**.

    So, a **Module** in sequana's parlance is a directory that contains a
    rule or a pipeline and associated files. There is currently no strict
    conventions for rule Modules except for their own rule file. However,
    pipeline Modules should have the following files:

        - A **snakemake** file named after the directory with the extension
          **.rules**
        - A **README.rst** file in restructured text format
        - An optional config file in YAML format named config.yaml.
          Although json format is possible, we use YAML throughout
          **sequana** for consistency. Rules do not have any but pipelines
          do. So if a pipeline does not provide a config.yaml, the one found
          in ./sequana/sequana/pipelines will be used.
        - a **requirements.txt**

    .. note:: Developers who wish to include new rules should refer to the
        Developer guide.

    .. note:: it is important that module's name should be used to name
        the directory and the rule/pipeline.

    The **Modules** are stored in sequana/rules and sequana/pipelines
    directories. The modules' names cannot be duplicated.

    Example::

        pipelines/test_pipe/test_pipe.rules
        pipelines/test_pipe/README.rst
        rules/rule1/rule1.rules
        rules/rule1/README.rst

    The :class:`Module` will ease the retrieval of information linked to a
    rule or pipeline. For instance if a pipeline has a config file, its path
    can be retrived easily::

        m = Module("quality_control")
        m.config

    This Module may be rule or pipeline, the method :meth:`is_pipeline` can
    be used to get that information.

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

    import sequana
    sequana.modules.keys()""".format(
                    name
                )
            )
        else:
            self._path = self._mf._paths[name]

        self._name = name

        self._snakefile = None
        self._description = None
        self._requirements = None

    def is_pipeline(self):
        """Return true is this module is a pipeline"""
        if self._name.startswith("pipeline:"):
            return True
        else:
            return False

    def _get_file(self, name):
        filename = os.sep.join((self._path, name))
        if os.path.exists(filename):
            return filename

    def __repr__(self):
        str = "Name: %s\n" % self._name
        str += "Path: %s\n" % self.path
        str += "Config: %s\n" % self.config
        str += "Cluster config: %s\n" % self.cluster_config
        str += "Schema for config file: %s\n" % self.schema_config
        str += "Multiqc config file: %s\n" % self.multiqc_config
        str += "requirements file: %s\n" % self.requirements
        str += "version: %s\n" % self.version
        return str

    def __str__(self):
        txt = "Rule **" + self.name + "**:\n" + self.description
        return txt

    def _get_version(self):
        if "/" in self.name:
            return self.name.split("/")[1]
        elif self.is_pipeline():
            import pkg_resources

            name = self.name.replace("pipeline:", "")
            ver = pkg_resources.require(f"sequana_{name}")[0].version
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

    def _get_cluster_config(self):
        # The default config file for that module
        return self._get_file("cluster_config.json")

    cluster_config = property(_get_cluster_config, doc="full path to the config cluster file of the module")

    def _get_readme(self):
        return self._get_file("README.rst")

    readme = property(_get_readme, doc="full path to the README file of the module")

    def _get_overview(self):
        result = "no information. For developers: please fix the pipeline "
        result += "README.rst file by adding an :Overview: field"
        for this in self.description.split("\n"):
            if this.startswith(":Overview:"):
                try:
                    result = this.split(":Overview:")[1].strip()
                except IndexError:
                    result += "Bad format in :Overview: field"
        return result

    overview = property(_get_overview)

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
        if self._get_file("requirements.txt"):
            self._requirements = self._get_file("requirements.txt")
            return self._requirements

    requirements = property(_get_requirements, doc="list of requirements")

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
        with open(self.requirements, "r") as fh:
            data = fh.read()
            datalist = [this.strip() for this in data.split("\n") if len(this.strip()) > 0]
            reqlist = []
            for this in datalist:
                if this.startswith("-"):
                    req = this.split("-")[1].split()[0].strip()
                    if req.startswith("["):
                        req = req.replace("[", "")
                        req = req.replace("]", "")
                        pipelines.append(req)
                    else:
                        reqlist.append(req)
                else:
                    req = this.strip()
                    if req.startswith("["):
                        req = req.replace("[", "")
                        req = req.replace("]", "")
                        pipelines.append(req)
                    else:
                        reqlist.append(req)

        # Check the pipelines independently
        for pipeline in pipelines:
            Module(pipeline).check()

        for req in reqlist:
            # It is either a Python package or an executable
            if req.startswith("#"):
                continue
            try:
                easydev.shellcmd(f"which {req}")
                logger.debug(f"Found {req} executable")
            except Exception:
                # is this a Python code ?
                if len(easydev.get_dependencies(req)) == 0:
                    executable = False
                    missing.append(req)
                else:
                    logger.info(f"{req} python package")
        return executable, missing

    def check(self, mode="warning"):

        executable, missing = self.is_executable()

        if executable is False:
            # _ = self.is_executable()
            missing = " ".join(missing)
            txt = f"""Some executable or Python packages are not available: {missing}
Some functionalities may not work. Consider adding them with  conda or damona (singularity based): 

            pip install damona
            damona install sequana_tools 
            damona activate sequana_tools

            """

            if mode == "warning":
                logger.critical(txt)
            elif mode == "error":  # pragma: no cover
                txt += "you may want to use \n conda install {missing};"
                for this in missing:
                    txt += "- %s\n" % this
                raise ValueError(txt)

    def _get_description(self):
        try:
            with open(self.readme) as fh:
                self._description = fh.read()
        except TypeError:
            self._description = "no description"
        return self._description

    description = property(_get_description, doc=("Content of the README file associated with "))

    def md5(self):
        """return md5 of snakefile and its default configuration file

        ::

            >>> from sequana import snaketools as sm
            >>> m = sm.Module("variant_calling")
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
        module = Module(name)
        filename = module.snakefile
        if filename:
            yield name, filename


# dictionary with module names as keys and fullpath to the Snakefile as values
modules = {name: filename for name, filename in _get_modules_snakefiles()}

# list of pipeline names found in the list of modules
pipeline_names = [m for m in modules if Module(m).is_pipeline()]
