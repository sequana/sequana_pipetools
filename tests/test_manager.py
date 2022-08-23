import pytest

from easydev import AttrDict

from sequana_pipetools import SequanaManager
from sequana_pipetools import SequanaConfig
from sequana_pipetools.sequana_manager import get_pipeline_location

from . import test_dir


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
    pm = SequanaManager(
        AttrDict(**{"version": False, "workdir": wkdir, 'level': "INFO", "use_singularity": False,
                    "jobs": 1, "run_mode": "local", "profle":"local", "force": True, "profile": None}),
        "fastqc")
    pm.config.config.input_directory = f"{test_dir}/data/"
    pm.config.config.input_pattern = "Hm2*gz"
    pm.config.config.input_readtag = "_R[12]_"

    pm.setup()
    pm.teardown()
    


    # We can now try to do it again fro the existing project itself
    pm = SequanaManager(
        AttrDict(**{"version": False, "workdir": wkdir, 'level': "INFO",
                    "jobs": 1, "run_mode": None, "force": True, "use_singularity": False,
                    "from_project": wkdir, "profile": None}),
        "fastqc")

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
    pm.config.config['requirements'] = []
    pm.teardown()


def test_sequana_manager_wrong_input(tmpdir):
    wkdir = tmpdir.mkdir("wkdir")

    # normal behaviour
    pm = SequanaManager(
        AttrDict(**{"version": False, "workdir": wkdir, 'level': "INFO", 
                    "use_singularity": False,
                    "jobs":1, "run_mode": None, "force": True}),
        "fastqc")
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

    pm = SequanaManager(
        AttrDict(**{"version": False, "workdir": wkdir, 'level': "INFO",
                    "jobs": 1, "run_mode": "slurm", "profile": "slurm", "force": True, "use_singularity": False,
                     "profile": None}),
        "fastqc")

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
    try:
        pm = SequanaManager(
            AttrDict(**{"version": True, "workdir": wkdir,'level':"INFO",
                        "jobs":1, "run_mode": None, "force": True}),
            "fastqc")
        assert False
    except SystemExit:
        assert True


def test_wrong_pipeline(tmpdir):
    wkdir = tmpdir.mkdir("wkdir")
    try:
        SequanaManager(
            AttrDict(**{"version": False, "workdir": wkdir, 'level': "INFO",
                        "jobs": 1, "run_mode": None, "force": True}),
            "wrong")
        assert False
    except SystemExit:
        assert True


def test_copy_requirements(tmpdir):
    # We need several cases:
    # 1- http
    # 3- an existing file elsewhere (here just a temporary file)
    # 4- an existing file in the same directory as the target dir

    # Case 3: a temporary file
    tmp_require = tmpdir.join("requirement.txt")

    requirements = [
        #"phiX174.fa",
        str(tmp_require),
        "https://raw.githubusercontent.com/sequana/sequana/master/README.rst",
        "__init__.py", "setup.py"
    ]

    wkdir = tmpdir.mkdir("wkdir")

    # normal behaviour
    pm = SequanaManager(
        AttrDict(**{"version": False, "workdir": str(wkdir), 'level': "INFO", "use_singularity": False,
                    "jobs": 1, "run_mode": None, "force": True, "profile": None}),
        "fastqc")
    pm.config.config.input_directory = f"{test_dir}/data/"
    pm.config.config.input_pattern = "Hm2*gz"
    pm.config.config.input_readtag = "_R[12]_"
    pm.config.config.requirements = requirements
    pm.setup()
    pm.teardown()
