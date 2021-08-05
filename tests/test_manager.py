import os

from sequana_pipetools import SequanaManager
from sequana_pipetools import SequanaConfig
from sequana_pipetools import Module
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

    # normal behaviour
    from easydev import AttrDict
    pm = SequanaManager(
        AttrDict(**{"version": False, "workdir": wkdir, 
                    "jobs":1, "run_mode": None, "force": True}), 
        "quality_control")
    pm.config.config.input_directory = f"{test_dir}/data/"
    pm.config.config.input_pattern = f"Hm2*gz"

    pm.setup()
    pm.teardown()
    pm.check_fastq_files()


def test_location():
    get_pipeline_location("quality_control")

