from sequana_pipetools import slurm
from sequana_pipetools.scripts.slurm import main
import sys
import pytest

from . import test_dir

sharedir = f"{test_dir}/../data"


def test():
    with pytest.raises(SystemExit):
        dj = slurm.DebugJob(".")
        dj
    dj = slurm.DebugJob(sharedir)
    dj


def test_command():
    sys.argv = ["test", "--directory", sharedir]
    main()


def test_get_error_message():
    dj = slurm.DebugJob(sharedir)
    for x in dj.slurm_out:
        dj._get_error_message(x)
