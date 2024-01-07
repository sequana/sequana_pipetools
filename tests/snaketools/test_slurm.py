from pathlib import Path

import pytest

from sequana_pipetools.snaketools.slurm import SlurmParsing

from . import test_dir

sharedir = Path(f"{test_dir}/data")


def test_slurm():
    dj = SlurmParsing(sharedir / "slurm_error1")
    print(dj)
    dj
    dj._report()
