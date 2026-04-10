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
import asyncio
import datetime
import glob
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import aiohttp
import colorlog
from easydev import CustomConfig

from sequana_pipetools import get_package_version
from sequana_pipetools.misc import url2hash
from sequana_pipetools.snaketools.profile import _is_v8, create_profile

from .misc import Colors
from .snaketools import Pipeline, SequanaConfig

logger = colorlog.getLogger(__name__)


class Wrapper:
    def __init__(self):
        # The .config/sequana is going to be created by the SequanaManager
        self._path = Path.home() / ".config" / "sequana" / "wrappers"

    def _get_path(self):
        return self._path

    repo_path = property(_get_path)

    def _get_prefixed_path(self):
        return f"git+file://{str(self._path)}"

    prefixed_path = property(_get_prefixed_path)

    def clone(self):  # pragma: no cover
        if not self.repo_path.exists():
            logger.info(f"Cloning sequana-wrappers into {self.repo_path}")
            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", "https://github.com/sequana/sequana-wrappers-lite.git", str(self.repo_path)],
                capture_output=True,
                text=True,
            )
            logger.debug(result.stdout)
            logger.debug(result.stderr)
        else:
            logger.info(f"Updating sequana-wrappers into {self.repo_path}")
            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(["git", "pull"], cwd=self.repo_path, capture_output=True, text=True)  # nosec
            logger.debug(result.stdout)
            logger.debug(result.stderr)


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
                apptainer_prefix = ""
                def __init__(self):
                    pass
            from sequana_pipetools import SequanaManager
            o = Options()
            pm = SequanaManager(o, "fastqc")


        The working_directory is used to copy the pipeline in it.

        """

        # Old argparse version provides a namespace with attributes;
        # new click version provides a dictionary — convert it here.
        if not hasattr(options, "version"):
            options = SimpleNamespace(**options)

        # the logger must be defined here because from a pipeline, it may not
        # have been defined yet.
        try:
            logger.setLevel(options.level)
        except AttributeError:  # pragma: no cover
            logger.warning("Your pipeline does not have a level option.")
            options.level = "INFO"

        self.options = options
        self.name = name

        # handy printer
        self.colors = Colors()

        # load the pipeline (to check it is possible and if it is a pipeline)
        try:
            self.module = Pipeline(f"{self.name}")
        except ValueError:
            logger.error(f"{self.name} does not seem to be installed or is not a valid pipeline")
            sys.exit(1)
        self.module.check()
        # self.module.is_executable()

        # If this is a pipeline, let us load its config file
        # Do we start from an existing project with a valid config file
        config_name = os.path.basename(self.module.config)
        self.config = None

        if not hasattr(options, "from_project"):
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

        # Set wrappers as attribute so that it may be changed by the
        # user/developer
        self.sequana_wrappers = os.environ.get(
            "SEQUANA_WRAPPERS", "https://raw.githubusercontent.com/sequana/sequana-wrappers/"
        )

        from rich.console import Console
        from rich.panel import Panel

        lines = [
            f"[bold cyan]Pipeline:[/bold cyan] sequana_{self.name}  (v{self._get_package_version()})",
            f"[bold cyan]Docs:    [/bold cyan] https://github.com/sequana/{self.name}",
            "[bold cyan]Website: [/bold cyan] https://sequana.readthedocs.io",
        ]
        Console().print(Panel("\n".join(lines), title="Welcome to Sequana", border_style="bold blue", padding=(1, 2)))

        wrapper_factory = Wrapper()
        wrapper_factory.clone()
        self.sequana_wrappers = wrapper_factory.prefixed_path

        if self.options.apptainer_prefix:  # pragma: no cover
            self.apptainer_prefix = Path(self.options.apptainer_prefix).resolve()
            self.use_apptainer = True

            if self.apptainer_prefix.exists() is False:
                logger.warning(f"Creating {self.apptainer_prefix} to store containers (does not exist)")
                os.makedirs(self.apptainer_prefix)
            self.local_apptainers = False
        else:  # pragma: no cover
            self.apptainer_prefix = os.environ.get("SEQUANA_SINGULARITY_PREFIX", f"{self.workdir}/.sequana/apptainers")
            self.local_apptainers = True
            self.use_apptainer = False

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

    def _get_package_version(self):
        return get_package_version(f"sequana_{self.name}")

    def _get_sequana_version(self):
        return get_package_version("sequana")

    def fill_data_options(self):
        options = self.options
        cfg = self.config.config
        if options.from_project:
            if "--input-pattern" in sys.argv:
                cfg.input_pattern = options.input_pattern
            if "--input-directory" in sys.argv:
                cfg.input_directory = os.path.abspath(options.input_directory)
            if "--input-readtag" in sys.argv:
                cfg.input_readtag = options.input_readtag
            if "--exclude-pattern" in sys.argv:
                cfg.exclude_pattern = options.exclude_pattern
        else:
            cfg.input_pattern = options.input_pattern
            cfg.exclude_pattern = options.exclude_pattern
            cfg.input_readtag = options.input_readtag
            cfg.input_directory = os.path.abspath(options.input_directory)

    def setup(self):
        """Initialise the pipeline.

        - Create a directory (usually named after the pipeline name)
        - Copy the pipeline and associated files (e.g. config file)
        - Create a script in the directory ready to use

        """
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
                logger.warning(f"\u2757 Path {self.workdir} exists already but you set --force to overwrite it")
            else:  # pragma: no cover
                logger.error(f"Output path {self.workdir} exists already. Use --force to overwrite")
                sys.exit(1)
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

        # this code is just informative. Actual run is snaketools.pipeline_manager
        exclude_pattern = getattr(cfg, "exclude_pattern", None)
        if exclude_pattern:
            filenames = [x for x in filenames if exclude_pattern not in x.split("/")[-1]]
        logger.info(
            f"\u2705 Found {len(filenames)} files matching your input  pattern ({cfg.input_pattern}) in {cfg.input_directory}"
        )

        if len(filenames) == 0:
            logger.critical(
                f"\u2757 Found no files with your matching pattern ({cfg.input_pattern}) in {cfg.input_directory}"
            )
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
        except (FileExistsError, PermissionError):  # pragma: no cover
            pass

        # the final command
        command_file = self.workdir / f"{self.name}.sh"
        snakefilename = os.path.basename(self.module.snakefile)

        # use profile command
        options = {
            "wrappers": self.sequana_wrappers,
            "jobs": self.options.jobs,
            "forceall": False,
            "keep_going": getattr(self.options, "keep_going", False),
            "use_apptainer": self.use_apptainer,
        }

        if self.use_apptainer:  # pragma: no cover
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
            # Both v7 and v8 use programmatic YAML (ruamel.yaml handles quoting)
            options["apptainer_args"] = f"-e -B {home} {self.options.apptainer_args}".strip()
        else:
            options["apptainer_prefix"] = ""
            options["apptainer_args"] = ""

        if self.options.profile == "slurm":
            # add slurm options; v7 YAML template needs quoted memory value, v8 programmatic does not
            memory_value = self.options.slurm_memory if _is_v8() else f"'{self.options.slurm_memory}'"
            options.update(
                {
                    "partition": "common",
                    "qos": "normal",
                    "memory": memory_value,
                }
            )
            if self.options.slurm_queue != "common":
                options.update({"partition": self.options.slurm_queue, "qos": self.options.slurm_queue})

        profile_dir = create_profile(self.workdir, self.options.profile, **options)

        use_monitor = getattr(self.options, "monitor", False)
        if use_monitor:
            pipeline_version = self._get_package_version()
            command = (
                "#!/bin/bash\n"
                "sequana_pipetools_monitor"
                f" --snakefile {snakefilename}"
                f" --profile {profile_dir}"
                f" --name {self.name}"
                f" --version {pipeline_version}"
            )
        else:
            command = (
                "#!/bin/bash\nset -o pipefail\n"
                f"snakemake -s {snakefilename} --profile {profile_dir}"
                " 2>&1 | tee .sequana/snakemake.log"
            )

        command_file.write_text(command)
        command_file.chmod(command_file.stat().st_mode | 0o111)

        # create a runme.sh (easier for end-user ?)
        command_file = self.workdir / "runme.sh"
        command_file.write_text(command)
        command_file.chmod(command_file.stat().st_mode | 0o111)

        # README
        command_file = self.workdir / "README"
        command_file.write_text(
            f"Execute runme.sh or {self.name}.sh. If you interrrupt a run, you may need to unlock the directory. Execute unlock.sh. For fine tuning, edit config.yaml (pipeline-related) or profile_config.yaml (snakemake-related). "
        )

        try:
            os.symlink(Path(profile_dir) / "config.yaml", self.workdir / "profile_config.yaml")
        except FileExistsError:  # pragma: no cover
            pass

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
            mqc_config = self.module.multiqc_config
            shutil.copy(mqc_config, self.workdir / ".sequana/multiqc_config.yaml")
            try:
                os.symlink(".sequana/multiqc_config.yaml", self.workdir / "multiqc_config.yaml")
            except FileExistsError:  # pragma: no cover
                pass

        # the rules if any
        if self.module.rules:
            try:
                shutil.copytree(self.module.rules, self.workdir / "rules")
            except FileExistsError:
                if self.options.force:
                    shutil.rmtree(self.workdir / "rules")
                    shutil.copytree(self.module.rules, self.workdir / "rules")

        if self.module.requirements and os.path.exists(self.module.requirements):
            with open(self.workdir / ".sequana" / "tools.txt", "w") as fout:
                for x in self.module.requirements_names:
                    fout.write(f"{x}\n")

        # the schema if any
        if self.module.schema_config:
            schema_name = os.path.basename(self.module.schema_config)
            shutil.copy(self.module.schema_config, self.workdir / ".sequana/schema.yaml")
            try:
                os.symlink(".sequana/schema.yaml", self.workdir / "schema.yaml")
            except FileExistsError:  # pragma: no cover
                pass

            # This is the place where we can check the entire validity of the
            # inputs based on the schema
            if check_schema:
                cfg = SequanaConfig(f"{self.workdir}/{config_name}")
                cfg.check_config_with_schema(f"{self.workdir}/{schema_name}")

        # if --apptainer-prefix is set, we need to download images for the users
        # Sequana pipelines will store images in Zenodo website (via damona).
        # introspecting sections written as:
        # container:
        #     "https://...image.img"
        if self.use_apptainer:  # pragma: no cover
            self._download_zenodo_images()

        from rich.console import Console
        from rich.panel import Panel

        if self.options.profile == "slurm":
            run_cmd = f"cd {self.workdir}; sbatch {self.name}.sh"
        else:
            run_cmd = f"cd {self.workdir}; ./{self.name}.sh"

        lines = [
            f"[bold]1.[/bold] Review the pipeline config:\n   [cyan]{self.workdir}/{config_name}[/cyan]",
            f"[bold]2.[/bold] Tune snakemake settings:\n   [cyan]{self.workdir}/.sequana/profile_{self.options.profile}/config.yaml[/cyan]",
            f"[bold]3.[/bold] Launch the pipeline:\n   [green]{run_cmd}[/green]",
        ]
        Console().print(Panel("\n".join(lines), title="Next steps", border_style="bold magenta", padding=(1, 2)))

        # Save an info.txt with the command used
        with open(self.workdir / ".sequana" / "info.txt", "w") as fout:
            from . import version

            fout.write(f"# sequana_pipetools version: {version}\n")
            fout.write(f"# sequana_{self.name} version: {self._get_package_version()}\n")
            fout.write(f"# sequana version: {self._get_sequana_version()}\n")

            fout.write(f"# python version: {sys.version.split()[0]}\n")
            fout.write(f"# Date: {datetime.datetime.now()}\n")
            cmd1 = os.path.basename(sys.argv[0])
            fout.write(" ".join([cmd1] + sys.argv[1:]))

        # Save unlock.sh
        unlock_cores = "--cores 1" if _is_v8() else "-j 1"
        script = f"#!/bin/sh\nsnakemake -s {snakefilename} --unlock {unlock_cores}"
        (self.workdir / "unlock.sh").write_text(script)

        if shutil.which("pip"):
            cmd = f"{sys.executable} -m pip freeze"
            with open(f"{self.workdir}/.sequana/pip.yml", "w") as fout:
                subprocess.call(cmd.split(), stdout=fout)
            logger.debug("Saved your pip environment into pip.txt")
        else:  # pragma: no cover
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
                            " using the following command: \n\t sequana_pipetools --completion {}\n\n"
                        )
                        msg = msg.format(version, self.name, self._get_package_version(), completion, self.name)
                        logger.info(msg)

        else:
            logger.info(f"Note that completion is possible with sequana_pipetools --completion {self.name}")

        if getattr(self.options, "execute", False):
            self.run()

    def run(self):
        """Execute the pipeline script from the working directory.

        For local runs, executes ``{name}.sh`` with bash.
        For SLURM, submits ``{name}.sh`` via sbatch.
        """
        script = f"{self.name}.sh"
        if self.options.profile == "slurm":
            cmd = ["sbatch", script]
        else:
            cmd = ["bash", script]

        logger.info(f"Launching pipeline: {' '.join(cmd)} (in {self.workdir})")
        subprocess.run(cmd, cwd=self.workdir)  # nosec

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
        if not section_name.endswith(":"):
            raise ValueError(f"section_name must end with ':', got: {section_name!r}")

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
        logger.info(f"Container mode is on. Downloading containers in {self.apptainer_prefix}")
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

        # fetch registry for MD5 verification (unless --no-md5-check)
        check_md5 = not getattr(self.options, "no_md5_check", False)
        md5_by_url = {}
        if check_md5:
            md5_by_url = _fetch_registry_md5s()
            if md5_by_url:
                logger.info(f"Fetched damona registry ({len(md5_by_url)} containers with MD5)")
            else:
                logger.warning("MD5 verification skipped (could not fetch registry)")

        # directory where images will be saved
        os.makedirs(self.apptainer_prefix, exist_ok=True)

        count = 0
        files_to_download = []
        all_outfiles = []

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
            except (FileExistsError, PermissionError):  # pragma: no cover
                pass

            all_outfiles.append(outfile)
            container = url.split("/")[-1]
            if os.path.exists(outfile):
                # verify MD5 if we have a reference from the registry
                expected_md5 = md5_by_url.get(url)
                if expected_md5:
                    actual_md5 = _md5sum(outfile)
                    if actual_md5 != expected_md5:
                        logger.warning(
                            f"MD5 mismatch for {container} "
                            f"(expected {expected_md5}, got {actual_md5}). Re-downloading."
                        )
                        os.remove(outfile)
                        files_to_download.append((url, outfile, count))
                        count += 1
                    else:
                        logger.info(f"\u2705 Found container {container} (MD5 verified)")
                else:
                    logger.info(f"\u2705 Found container {container}")
            else:
                files_to_download.append((url, outfile, count))
                count += 1
                logger.info(f"Preparing {Path(url).name}")

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

        total_size = sum(Path(f).stat().st_size for f in all_outfiles if Path(f).is_file())
        total_size_mb = round(total_size / 1024 / 1024)
        if total_size_mb >= 1000:
            logger.info(f"Total container size: {total_size_mb / 1024:.1f} Gb")
        else:
            logger.info(f"Total container size: {total_size_mb} Mb")


def _md5sum(filepath, chunk=65536):
    """Compute MD5 checksum of a file."""
    h = hashlib.md5(usedforsecurity=False)
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _fetch_registry_md5s():
    """Fetch the damona registry and return a dict mapping download URLs to md5sums."""
    import yaml

    url = "https://raw.githubusercontent.com/cokelaer/damona/main/damona/software/registry.yaml"
    try:
        import requests

        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        registry = yaml.safe_load(resp.text)
    except Exception as e:
        logger.warning(f"Could not fetch damona registry for MD5 verification: {e}")
        return {}

    md5_by_url = {}
    for _tool, info in registry.items():
        if not isinstance(info, dict):
            continue
        for _version, release in info.get("releases", {}).items():
            if not isinstance(release, dict):
                continue
            dl = release.get("download", "")
            md5 = release.get("md5sum", "")
            if dl and md5:
                md5_by_url[dl] = md5
    return md5_by_url


def multiple_downloads(files_to_download, timeout=3600):
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=40, complete_style="yellow", finished_style="bold green"),
        "[progress.percentage]{task.percentage:>3.0f}%",
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )

    async def download(session, url, name, _position):
        async with session.get(url, timeout=timeout) as resp:
            total = int(resp.headers.get("content-length", 0))
            task = progress.add_task(url.split("/")[-1], total=total)
            with open(name, "wb") as fd:
                async for chunk in resp.content.iter_chunked(4096):
                    fd.write(chunk)
                    progress.advance(task, len(chunk))

    async def download_all(files_to_download):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as session:
            with progress:
                for data in files_to_download:
                    await download(session, *data)

    asyncio.run(download_all(files_to_download))
