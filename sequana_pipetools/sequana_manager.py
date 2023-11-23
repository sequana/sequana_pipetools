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
import shutil
import subprocess
import pkg_resources
import sys
import aiohttp
import asyncio
from shutil import which
from urllib.request import urlretrieve
from pathlib import Path

from tqdm.asyncio import tqdm

import colorlog
from easydev import CustomConfig, AttrDict

from sequana_pipetools.snaketools.profile import create_profile
from sequana_pipetools.misc import url2hash

from .misc import Colors, PipetoolsException, print_version
from .snaketools import Module, SequanaConfig

logger = colorlog.getLogger(__name__)


class SequanaManager:
    def __init__(self, options, name="undefined"):
        """
        :param options: an instance of :class:`Options`
        :param name: name of the pipeline. Must be a Sequana pipeline already installed.

        options must be an object Options with at least the following attributes:

        ::

            class Options:
                level = 'INFO'
                version = False
                workdir = "fastqc"
                job=1
                force = True
                use_apptainer = False
                apptainer_prefix = ""
                def __init__(self):
                    pass
            from sequana_pipetools import SequanaManager
            o = Options()
            pm = SequanaManager(o, "fastqc")


        The working_directory is used to copy the pipeline in it.

        """

        # Old argparse version provide a structure with attributes
        # whereas new click provides a dictionary. Here we covnert the
        # dictionary into a attribute/class like using AttrDict


        try:
            options.version
        except AttributeError:
            options = AttrDict(**options)

        # the logger must be defined here because from a pipeline, it may not
        # have been defined yet.
        try:
            logger.setLevel(options.level)
        except AttributeError:
            logger.warning("Your pipeline does not have a level option.")
            options.level = "INFO"


        self.options = options
        self.name = name

        # handy printer
        self.colors = Colors()

        # load the pipeline (to check it is possible and if it is a pipeline)
        try:
            self.module = Module(f"pipeline:{self.name}")
        except ValueError:
            logger.error(f"{self.name} does not seem to be installed or is not a valid pipeline")
            sys.exit(1)
        self.module.check()
        # self.module.is_executable()

        # If this is a pipeline, let us load its config file
        # Do we start from an existing project with a valid config file
        config_name = os.path.basename(self.module.config)
        self.config = None

        try:
            options.from_project
        except AttributeError:
            options.from_project = False

        if options.from_project:
            possible_filenames = (
                # from project tries to find a valid config.yaml
                # options.from_project,  # exact config file path
                f"{options.from_project}/{config_name}",  # config file in project path
                f"{options.from_project}/.sequana/{config_name}",  # config file in .sequana dir
            )
            for filename in possible_filenames:
                try:
                    self.config = SequanaConfig(filename)
                    logger.info(f"Reading existing config file {filename}")
                    break
                except FileNotFoundError:  # pragma: no cover
                    pass

            if not self.config:  # pragma: no cover
                raise FileNotFoundError(
                    "Could not find config.yaml in the project specified {}".format(options.from_project)
                )
        else:
            self.config = SequanaConfig(self.module.config)

        # the working directory
        self.workdir = Path(options.workdir)

        # define the data path of the pipeline
        self.datapath = self._get_package_location()

        # Set wrappers as attribute so that it may be changed by the
        # user/developer
        self.sequana_wrappers = os.environ.get(
            "SEQUANA_WRAPPERS", "https://raw.githubusercontent.com/sequana/sequana-wrappers/"
        )

        if self.options.apptainer_prefix:  # pragma: no cover
            self.apptainer_prefix = self.options.apptainer_prefix
            self.local_apptainers = False
        else:  # pragma: no cover
            self.apptainer_prefix = os.environ.get("SEQUANA_SINGULARITY_PREFIX", f"{self.workdir}/.sequana/apptainers")
            self.local_apptainers = True

    def exists(self, filename, exit_on_error=True, warning_only=False):  # pragma: no cover
        """This is a convenient function to check if a directory/file exists

        Used in the main.py of all pipelines when setting the working directory
        """
        if not os.path.exists(filename):
            if warning_only:
                logger.warning(f"{filename} file does not exists")
            else:
                logger.error(f"{filename} file does not exists")
                if exit_on_error:
                    sys.exit(1)
            return False
        return True

    def _get_package_location(self):
        import site

        for site_package in site.getsitepackages():

            site_path = Path(site_package)
            pipeline_path = site_path / "sequana_pipelines" / self.name
            if pipeline_path.exists():
                return pipeline_path / "data"

            # if _ is found in the name, it may be replaced by dash -
            name = self.name.replace("_", "-")

            # python egg seems deprecated, editable mode create a .pth file
            pth_file = site_path / f"{name}.pth"
            if not pth_file.exists():
                # some packages have "sequana_name"
                pth_file = site_path / f"sequana_{name}.pth"
            try:
                pipeline_path = Path(pth_file.read_text().rstrip()) / "sequana_pipelines" / self.name
                if pipeline_path.exists:
                    return pipeline_path / "data"
            except FileNotFoundError:
                pass

            # if it does not exist, this may be a "develop" mode.
            pipeline_path = Path(site_package) / f"sequana-{name}.egg-link"
            if pipeline_path.exists():
                return pipeline_path / "data"


        logger.error(f"package provided ({self.name}) not installed.")
        raise PipetoolsException

    def _get_package_version(self):
        try:
            ver = pkg_resources.require("sequana_{}".format(self.name))[0].version
        except pkg_resources.DistributionNotFound:
            # check if the package exists
            ver = pkg_resources.require(self.name)[0].version
        return ver

    def _get_sequana_version(self):
        try:
            ver = pkg_resources.require(f"sequana.{self.name}")[0].version
            return ver
        except pkg_resources.DistributionNotFound:  # pragma: no cover
            return "not installed"

    def error_report(self):
        """Try to report error from slurm"""
        from sequana_pipetools.errors import PipeError
        p = PipeError("fastqc")
        p.status()

    def _guess_scheduler(self):

        if which("sbatch") and which("srun"):  # pragma: no cover
            return "slurm"
        else:
            return "local"

    def setup(self):
        """Initialise the pipeline.

        - Create a directory (usually named after the pipeline name)
        - Copy the pipeline and associated files (e.g. config file)
        - Create a script in the directory ready to use


        """
        # First we create the beginning of the command with the optional
        # parameters for a run on a SLURM scheduler
        logger.info("Welcome to Sequana pipelines suite (https://sequana.readthedocs.io)")
        logger.info(" - Found an issue, have a question: https://tinyurl.com/2bh6frp2 ")
        logger.info(f" - more about this pipeline on https://github.com/sequana/{self.name} ")

        snakefilename = os.path.basename(self.module.snakefile)
        self.command = f"#!/bin/bash\nsnakemake -s {snakefilename} "

        if self.sequana_wrappers:
            self.command += f" --wrapper-prefix {self.sequana_wrappers} "
            logger.info(f"Using sequana-wrappers from {self.sequana_wrappers}")

        if self.options.use_apptainer:  # pragma: no cover

            # --home directory is set by snakemake using getcwd(), which prevent the
            # /home/user/ to be seen somehow. Therefore, we bind the /home manually.
            # We could have reset --home /home but we may have a side effect with snakemake.
            # We also add the -e to make sure a clean environment is used. This will avoid
            # unwanted side effect. We also appdn any user apptainer arguments.
            home = str(Path.home())
            apptainer_args = f"--singularity-args=' -e -B {home} {self.options.apptainer_args}'"

            # to add to the main command
            self.command += f" --use-singularity {apptainer_args}"

            # finally, the prefix where images are stored
            if self.local_apptainers:
                self.command += " --singularity-prefix .sequana/apptainers"
            else:
                if Path(self.apptainer_prefix ).is_absolute():
                    self.command += f" --singularity-prefix {self.apptainer_prefix} "
                else:
                    # if we set prefix to e.g. ./images then in the pipeline/script.sh,
                    # the prefix is also ./images whereas it should be ../images
                    self.command += f" --singularity-prefix ../{self.apptainer_prefix} "

        # set up core/jobs options
        if self.options.profile == "local":
            self.command += " -p --cores {} ".format(self.options.jobs)
        else:
            self.command += " -p --jobs {}".format(self.options.jobs)


        # This should be in the setup, not in the teardown since we may want to
        # copy files when creating the pipeline. This is the case e.g. in the
        # rnaseq pipeline. It is a bit annoying since if there is failure
        # between setup and teardown, the directories are created but no way to
        # fix that.
        self._create_directories()

    def _create_directories(self):
        # Now we create the directory to store the config/pipeline
        if self.workdir.exists():
            if self.options.force:
                logger.warning(f"Path {self.workdir} exists already but you set --force to overwrite it")
            else:  # pragma: no cover
                logger.error(f"Output path {self.workdir} exists already. Use --force to overwrite")
                sys.exit()
        else:
            self.workdir.mkdir()

        # Now we create the directory to store some info in
        # working_directory/.sequana for book-keeping and reproducibility
        hidden_dir = self.workdir / ".sequana"
        if not hidden_dir.exists():
            hidden_dir.mkdir()

    def check_input_files(self, stop_on_error=True):
        # Sanity checks
        cfg = self.config.config

        filenames = glob.glob(cfg.input_directory + os.sep + cfg.input_pattern)
        logger.info(f"Found {len(filenames)} files matching your input  pattern ({cfg.input_pattern})")

        if len(filenames) == 0:
            logger.critical(f"Found no files with your matching pattern ({cfg.input_pattern}) in {cfg.input_directory}")
            if "*" not in cfg.input_pattern and "?" not in cfg.input_pattern:
                logger.critical("No wildcard used in your input pattern, please use a * or ? character")
            if stop_on_error:
                sys.exit(1)

    def teardown(self, check_schema=True, check_input_files=True):
        """Save all files required to run the pipeline and perform sanity checks


        We copy the following files into the working directory:

        * the config file (config.yaml)
        * a NAME.sh that contains the snakemake command
        * the Snakefile (NAME.rules)

        For book-keeping and some parts of the pipelines, we copied the config
        file and its snakefile into the .sequana directory. We also copy
        the logo.png file if present into this .sequana directory

        and if present:

        * multiqc_config file for mutliqc reports
        * the schema.yaml file used to check the content of the
          config.yaml file

        """

        if check_input_files:
            self.check_input_files()

        # the config file
        self.config._update_yaml()
        config_name = os.path.basename(self.module.config)
        self.config.save(self.workdir / f".sequana/{config_name}")
        try:
            os.symlink(f".sequana/{config_name}", f"{self.workdir}/{config_name}")
        except FileExistsError:  # pragma: no cover
            pass

        # the final command
        command_file = self.workdir / f"{self.name}.sh"
        snakefilename = os.path.basename(self.module.snakefile)


        # use profile command
        options = {
            "wrappers": self.sequana_wrappers,
            "jobs": self.options.jobs,
            "forceall": False,
            "use_apptainer": self.options.use_apptainer,
        }

        if self.options.use_apptainer:  # pragma: no cover
            if self.local_apptainers:
                options["apptainer_prefix"] = ".sequana/apptainers"
            else:
                options["apptainer_prefix"] = self.apptainer_prefix

            # --home directory is set by snakemake using getcwd(), which prevent the
            # /home/user/ to be seen somehow. Therefore, we bind the /home manually.
            # We could have reset --home /home but we may have a side effect with snakemake.
            # We also add the -e to make sure a clean environment is used. This will avoid
            # unwanted side effect. We also appdn any user apptainer arguments.
            home = str(Path.home())
            options["apptainer_args"] = f" ' -e -B {home} {self.options.apptainer_args}'"
        else:
            options["apptainer_prefix"] = ""
            options["apptainer_args"] = ""

        if self.options.profile == "slurm":
            # add slurm options
            options.update(
                {
                    "partition": f"common",
                    "qos": "normal",
                    "memory": f"'{self.options.slurm_memory}'",  # quotes needed to avoid error in profile (° ͜ʖ °)
                }
            )
            if self.options.slurm_queue != "common":
                options.update({"partition": self.options.slurm_queue, "qos": self.options.slurm_queue})

        profile_dir = create_profile(self.workdir, self.options.profile, **options)
        command = f"#!/bin/bash\nsnakemake -s {snakefilename} --profile {profile_dir}"
        command_file.write_text(command)

        # the snakefile
        shutil.copy(self.module.snakefile, self.workdir / ".sequana")
        try:
            os.symlink(f".sequana/{snakefilename}", self.workdir / f"{snakefilename}")
        except FileExistsError:  # pragma: no cover
            pass

        # the logo if any
        if self.module.logo:
            shutil.copy(self.module.logo, self.workdir / ".sequana")

        # the multiqc if any
        if self.module.multiqc_config:
            shutil.copy(self.module.multiqc_config, self.workdir)

        # the rules if any
        if self.module.rules:
            try:
                shutil.copytree(self.module.rules, self.workdir / "rules")
            except FileExistsError:
                if self.options.force:
                    shutil.rmtree(self.workdir / "rules")
                    shutil.copytree(self.module.rules, self.workdir / "rules")

        # the requirements (standalone) and version
        infile = self.workdir / ".sequana" / "tools.txt"

        if self.module.requirements and os.path.exists(infile):
            with open(self.workdir / ".sequana" / "tools.txt", "w") as fout:
                for x in self.module.requirements_names:
                    fout.write(f"{x}\n")

        # the schema if any
        if self.module.schema_config:
            schema_name = os.path.basename(self.module.schema_config)
            shutil.copy(self.module.schema_config, self.workdir)

            # This is the place where we can check the entire validity of the
            # inputs based on the schema
            if check_schema:
                cfg = SequanaConfig(f"{self.workdir}/{config_name}")
                cfg.check_config_with_schema(f"{self.workdir}/{schema_name}")

        # if --use-apptainer is set, we need to download images for the users
        # Sequana pipelines will store images in Zenodo website (via damona).
        # introspecting sections written as:
        # container:
        #     "https://...image.img"
        if self.options.use_apptainer:  # pragma: no cover
            self._download_zenodo_images()


        # some information
        msg = "Please check the script in {}/{}.sh and "
        msg += f"the configuration file in {{}}/{config_name}.\n"
        print(self.colors.purple(msg.format(self.workdir, self.name, self.workdir)))

        msg = "Once ready, execute the script {}.sh using \n\n\t".format(self.name)
        if self.options.profile == "slurm":
            msg += "cd {}; sbatch {}.sh\n\n".format(self.workdir, self.name)
        else:
            msg += "cd {}; sh {}.sh\n\n".format(self.workdir, self.name)
        msg += f"You may tune extra parameters related to snakemake in {self.workdir}/{self.name}/.sequana/profile_{self.options.profile}"
        print(self.colors.purple(msg))

        # Save an info.txt with the command used
        with open(self.workdir / ".sequana" / "info.txt", "w") as fout:
            from . import version

            fout.write(f"# sequana_pipetools version: {version}\n")
            fout.write(f"# sequana_{self.name} version: {self._get_package_version()}\n")
            fout.write(f"# sequana version: {self._get_sequana_version()}\n")
            cmd1 = os.path.basename(sys.argv[0])
            fout.write(" ".join([cmd1] + sys.argv[1:]))

        # Save unlock.sh
        with open(self.workdir / "unlock.sh", "w") as fout:
            fout.write(f"#!/bin/sh\nsnakemake -s {snakefilename} --unlock -j 1")

        # save environment

        if shutil.which("conda"):
            cmd = "conda list"
            with open(f"{self.workdir}/.sequana/env.yml", "w") as fout:
                subprocess.call(cmd.split(), stdout=fout)
            logger.debug("Saved your conda environment into env.yml")
        else:
            with open(f"{self.workdir}/.sequana/env.yml", "w") as fout:
                fout.write("conda not found")

        if shutil.which("pip"):
            cmd = f"{sys.executable} -m pip freeze"
            with open(f"{self.workdir}/.sequana/pip.yml", "w") as fout:
                subprocess.call(cmd.split(), stdout=fout)
            logger.debug("Saved your pip environment into pip.txt (conda not found)")
        else:
            with open(f"{self.workdir}/.sequana/pip.yml", "w") as fout:
                fout.write("pip not found")

        # General information

        configuration = CustomConfig("sequana", verbose=False)
        sequana_config_path = configuration.user_config_dir
        completion = sequana_config_path + "/pipelines/{}.sh".format(self.name)
        if os.path.exists(completion):
            with open(completion, "r") as fin:
                line = fin.readline()
                if line.startswith("#version:"):
                    version = line.split("#version:")[1].strip()
                    version = version.replace(">=", "").replace(">", "")
                    from packaging.version import Version

                    if Version(version) < Version(self._get_package_version()):  # pragma: no cover
                        msg = (
                            "The version {} of your completion file for the {} pipeline seems older than the installed"
                            " pipeline itself ({}). Please, consider updating the completion file {}"
                            " using the following command: \n\t sequana_completion --name {}\n"
                            "available in the sequana_pipetools package (pip install sequana_completion)"
                        )
                        msg = msg.format(version, self.name, self._get_package_version(), completion, self.name)
                        logger.info(msg)

        else:
            logger.info("A completion if possible with sequana_completion --name {}".format(self.name))

    def _get_section_content(self, filename, section_name):
        """searching for a given section (e.g. container)

        and extrct its content. This is for simple cases where
        content is made of one line. Two cases are supported

        case 1 (two lines)::

            container:
                "https:...."

        case 2 (one line)

            container: "https...."

        comments starting with # are allowed.
        """
        assert section_name.endswith(":")

        contents = []
        with open(filename, "r") as fin:
            previous = ""
            for line in fin.readlines():
                if line.strip().startswith("#") or not line.strip():
                    pass
                # case 1
                elif section_name in line:
                    content = line.replace(section_name, "").strip()
                    content = content.strip('"').strip("'")
                    if content:  # case 2
                        contents.append(content)
                elif previous == section_name:
                    # case 1
                    content = line.replace(section_name, "").strip()
                    content = content.strip('"').strip("'")
                    contents.append(content)

                # this is for case 1
                previous = line.strip()
        return contents

    def _download_zenodo_images(self):  # pragma: no cover
        """
        Looking for container: section, this downloads all container that are
        online (starting with https). Recursive function that also looks into the
        ./rules directories based on the include: section found in the main
        Snakefile.

        """
        logger.info(f"You set --use-apptainer. Downloading containers into {self.apptainer_prefix}")
        # first get the urls in the main snakefile
        urls = self._get_section_content(self.module.snakefile, "container:")
        urls = [x for x in urls if x.startswith("http")]

        # second get the urls from sub-rules if any
        # do we have sub modules / includes ?
        included_files = self._get_section_content(self.module.snakefile, "include:")

        # included_files may include former modules from sequana. Need to keep only
        # actual files ending in .rules and .smk
        included_files = [x for x in included_files if x.endswith((".smk", ".rules"))]

        # for back compatibility, we scan the pipeline looking for container that start with http
        for included_file in included_files:
            suburls = self._get_section_content(Path(self.module.snakefile).parent / included_file, "container:")
            suburls = [x for x in suburls if x.startswith("http")]
            urls.extend(suburls)

        # but more generally, we wish to retrieve the containers URLs from the config file
        apps = self.config.config.get("apptainers", {})
        urls.extend((x for x in apps.values() if x.strip()))

        # make sure there are unique URLs
        urls = set(urls)

        # directory where images will be saved
        os.makedirs(self.apptainer_prefix, exist_ok=True)

        count = 0
        files_to_download = []

        # define the URLs and the output filename. 
        for url in urls:
            # get file name and hash name. The hash name is required by snakemake
            # but keeping original name helps debugging
            name = Path(url).name
            hashname = url2hash(url)

            # URL from damona/sequana ends with .img extension.
            # snakemake expected .simg hence but hasname above uses the original name.

            outfile = f"{self.apptainer_prefix}/{name}"
            linkfile = f"{self.apptainer_prefix}/{hashname}.simg"

            try:
                Path(linkfile).symlink_to(f"{name}")
            except FileExistsError:
                pass

            if os.path.exists(outfile):
                logger.info(f"Found corresponding image of {url} in {outfile}")
            else:
                files_to_download.append((url, outfile, count))
                count += 1
                logger.info(f"Preparing {url} for download")

        try:  # try an asynchrone downloads
            multiple_downloads(files_to_download)
        except (KeyboardInterrupt, asyncio.TimeoutError):
            logger.info("The download was interrupted or network was too slow. Removing partially downloaded files")
            for values in files_to_download:
                filename = values[1]
                Path(filename).unlink()
            logger.critical(
                "Keep going but your pipeline will probably not be fully executable since images could not be downloaded"
            )


def multiple_downloads(files_to_download, timeout=3600):
    async def download(session, url, name, position):
        async with session.get(url, timeout=timeout) as resp:
            with tqdm.wrapattr(
                open(name, "wb"),
                "write",
                miniters=1,
                desc=url.split("/")[-1],
                total=int(resp.headers.get("content-length", 0)),
                position=position,
            ) as fout:
                async for chunk in resp.content.iter_chunked(4096):
                    fout.write(chunk)

    async def download_all(files_to_download):
        """data_to_download is a list of tuples
        each tuple contain the url to download, its output name, and a unique
        position for the progress bar."""
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as session:
            await asyncio.gather(*(download(session, *data) for data in files_to_download))

    asyncio.run(download_all(files_to_download))


def get_pipeline_location(pipeline_name):
    class Opt:
        pass

    options = Opt()
    options.workdir = "."
    options.version = False
    options.apptainer_prefix = ""
    p = SequanaManager(options, pipeline_name)
    return p._get_package_location()
