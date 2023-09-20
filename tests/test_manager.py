import pytest

from easydev import AttrDict

from sequana_pipetools import SequanaManager
from sequana_pipetools import SequanaConfig
from sequana_pipetools.sequana_manager import get_pipeline_location

import pkg_resources
from packaging.version import parse as parse_version


from . import test_dir


default_dict = {
    "version": False,
    "level": "INFO",
    "use_apptainer": False,
    "apptainer_prefix": "",
    "jobs": 1,
    "run_mode": "local",
    "profile": "local",
    "force": True,
}


def test_pipeline_manager():
    # test missing input_directory
    cfg = SequanaConfig({"version": "1.0.0"})
    try:
        pm = SequanaManager(cfg, "dummy")
        assert False
    except:
        assert True


def test_sequana_manager(tmpdir):
    wkdir = tmpdir.mkdir("wkdir")

    # normal behaviour. also to test profile
    dd = default_dict.copy()
    dd["workdir"] = wkdir
    pm = SequanaManager(AttrDict(**dd), "fastqc")
    pm.config.config.input_directory = f"{test_dir}/data/"
    pm.config.config.input_pattern = "Hm2*gz"
    pm.config.config.input_readtag = "_R[12]_"

    pm.setup()
    pm.teardown()

    # We can now try to do it again fro the existing project itself
    dd = default_dict.copy()
    dd["from_project"] = wkdir
    dd["workdir"] = wkdir
    pm = SequanaManager(AttrDict(**dd), "fastqc")

    pm.setup()

    # set slurm options manually
    pm.options.run_mode = "slurm"
    pm.options.slurm_queue = "common"
    pm.options.slurm_memory = "4000"
    pm.options.slurm_cores_per_job = 4
    pm.options.slurm_queue = "biomics"
    pm.setup()
    pm.teardown()

    # test requirements (even if it is empty)
    pm.config.config["requirements"] = []
    pm.teardown()


def test_sequana_manager_wrong_input(tmpdir):
    wkdir = tmpdir.mkdir("wkdir")

    # normal behaviour
    dd = default_dict.copy()
    dd["workdir"] = wkdir
    pm = SequanaManager(AttrDict(**dd), "fastqc")
    pm.config.config.input_directory = f"{test_dir}/data/"
    # no files will be found but by default
    pm.config.config.input_pattern = f"FFF*gz"
    pm.config.config.input_readtag = f"_R[12]_"

    try:
        pm.check_input_files()
        assert False
    except SystemExit:
        assert True


def test_scheduler(tmpdir):
    wkdir = tmpdir.mkdir("wkdir")

    dd = default_dict.copy()
    dd["run_mode"] = "slurm"
    dd["profile"] = "slurm"
    dd["workdir"] = wkdir

    pm = SequanaManager(AttrDict(**dd), "fastqc")

    def mock_scheduler(*args, **kwargs):
        return "slurm"

    pm._guess_scheduler = mock_scheduler

    pm.options.profile = "slurm"
    pm.options.slurm_memory = "4000"
    pm.options.slurm_cores_per_job = 4
    pm.options.slurm_queue = "biomics"
    pm.config.config.input_directory = f"{test_dir}/data/"
    pm.config.config.input_pattern = "Hm2*gz"
    pm.config.config.input_readtag = "_R[12]_"

    pm.setup()
    pm.teardown()


def test_location():
    get_pipeline_location("fastqc")
    with pytest.raises(SystemExit):
        get_pipeline_location("dummy")


def test_version(tmpdir):
    wkdir = tmpdir.mkdir("wkdir")
    with pytest.raises(SystemExit):
        dd = default_dict.copy()
        dd["version"] = True
        dd["workdir"] = wkdir
        pm = SequanaManager(AttrDict(**dd), "fastqc")


def test_wrong_pipeline(tmpdir):
    wkdir = tmpdir.mkdir("wkdir")
    try:
        dd = default_dict.copy()
        dd["workdir"] = wkdir
        SequanaManager(AttrDict(**dd), "wrong")
        assert False
    except SystemExit:
        assert True


def test_copy_requirements(tmpdir):
    # We need several cases:
    # 1- http
    # 3- an existing file elsewhere (here just a temporary file)
    # 4- an existing file in the same directory as the target dir

    # Case 3: a temporary file
    tmp_require = tmpdir.join("tmp.txt")

    requirements = [
        str(tmp_require),
        "https://raw.githubusercontent.com/sequana/sequana/main/README.rst",
        "__init__.py",
    ]

    wkdir = tmpdir.mkdir("wkdir")

    # normal behaviour
    dd = default_dict.copy()
    dd["workdir"] = wkdir
    pm = SequanaManager(AttrDict(**dd), "fastqc")
    pm.config.config.input_directory = f"{test_dir}/data/"
    pm.config.config.input_pattern = "Hm2*gz"
    pm.config.config.input_readtag = "_R[12]_"
    pm.config.config.sequana_wrappers = "v0.15.1"
    pm.config.config.requirements = requirements
    pm.setup()
    pm.teardown()


def test_pipeline_parse_containers(tmpdir):
    wkdir = tmpdir.mkdir("wkdir")
    dd = default_dict.copy()
    dd["workdir"] = wkdir
    dd["use_apptainer"]
    pm = SequanaManager(AttrDict(**dd), "fastqc")
    # fastqc uses 3 apptainers:

    fastqc_version = pkg_resources.get_distribution("sequana_fastqc").version

    if parse_version(fastqc_version) >= parse_version("1.6.0"):
        assert len(pm._get_section_content(pm.module.snakefile, "container:")) in [2, 3]
    else:
        assert len(pm._get_section_content(pm.module.snakefile, "container:")) == 0


def test_multiple_downloads(tmpdir):
    file1 = tmpdir.join("file1.txt")
    file2 = tmpdir.join("file2.txt")
    data = [
        ("https://raw.githubusercontent.com/sequana/sequana_pipetools/main/README.rst", file1, 0),
        ("https://raw.githubusercontent.com/sequana/sequana_pipetools/main/requirements.txt", file2, 1),
    ]
    from sequana_pipetools.sequana_manager import multiple_downloads

    multiple_downloads(data)
