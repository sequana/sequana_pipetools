from sequana_pipetools import slurm
import os
import sys



from . import test_dir

sharedir = f"{test_dir}/data"

def test():
    try:
        dj = slurm.DebugJob(".")
        dj
        assert False
    except:
        assert True
    dj = slurm.DebugJob(sharedir)
    dj


def test_command():
    sys.argv = ["test", "--directory", sharedir]
    slurm.main()


def test_get_error_message():
    dj = slurm.DebugJob(sharedir)
    for x in dj.slurm_out:
        dj._get_error_message(x)
