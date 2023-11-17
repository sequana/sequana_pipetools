from sequana_pipetools import slurm
from sequana_pipetools.scripts.slurm import main
import pytest

from . import test_dir

sharedir = f"{test_dir}/../data"

from click.testing import CliRunner

def test():
    with pytest.raises(SystemExit):
        dj = slurm.DebugJob(".")
        dj
    dj = slurm.DebugJob(sharedir)
    assert dj


def test_command():
    runner = CliRunner()
    results = runner.invoke(main, ['--directory', sharedir])
    assert results.exit_code == 0



def test_get_error_message():
    dj = slurm.DebugJob(sharedir)
    for x in dj.slurm_out:
        dj._get_error_message(x)
