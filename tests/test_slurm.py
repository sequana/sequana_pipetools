from sequana_pipetools.slurm import DebugJob
import pytest

from . import test_dir

sharedir = f"{test_dir}/data"


def test():
    try:
        dj = DebugJob(".")
        assert False
    except SystemExit:
        assert True
    dj = DebugJob(sharedir)
    assert dj


def test_get_error_message():
    dj = DebugJob(sharedir)
    dj
    dj._report()
    for x in dj.slurm_out:
        dj._get_error_message(x)
