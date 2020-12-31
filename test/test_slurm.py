from sequana_pipetools import slurm
import os
import sys

import pkg_resources
info = pkg_resources.get_distribution("sequana_pipetools")
sharedir = os.sep.join([info.location , "sequana_pipetools", 'data'])


def test():
    try:
        dj = slurm.DebugJob(".")
        print(dj)   
        assert False
    except:
        assert True
    dj = slurm.DebugJob(sharedir)
    print(dj)    

def test_command():
    sys.argv = ["test", "--directory", sharedir]
    slurm.main()
 


dj = slurm.DebugJob(sharedir)
print(dj)
