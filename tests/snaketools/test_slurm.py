from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sequana_pipetools.snaketools.slurm import SlurmParsing, SlurmStats

from . import test_dir

sharedir = Path(f"{test_dir}/data")


def test_slurm():
    dj = SlurmParsing(sharedir / "slurm_error1")
    print(dj)
    dj
    dj._report()

    dj = SlurmParsing(sharedir / "slurm_error_no_master")
    print(dj)
    dj
    dj._report()


@pytest.fixture
def mock_sacct_output():
    # This is the mock output for the sacct command, including the header
    return """
       MaxRSS  AllocCPUS    Elapsed    CPUTime
    ---------- ---------- ---------- ----------
                        1   00:00:24   00:00:24
       264364K          1   00:00:24   00:00:24
           36K          1   00:00:24   00:00:24
    """


def test_parse_sacct_output(mock_sacct_output):
    # Initialize SlurmStats object with dummy parameters
    slurm_stats = SlurmStats(working_directory=".", logs_directory="logs")

    # Test the _parse_sacct_output method
    job_info = slurm_stats._parse_sacct_output(mock_sacct_output)

    # Assert the parsing is correct
    assert job_info == [0.252117, 1, "00:00:24", "00:00:24"]


@patch("subprocess.run")
def test_slurm_stats_with_mocked_sacct(mock_run, mock_sacct_output, tmpdir):
    # Mock the subprocess.run method
    mock_run.return_value = MagicMock(stdout=mock_sacct_output.encode("utf-8"), returncode=0)

    # Initialize SlurmStats object with dummy parameters
    slurm_stats = SlurmStats(working_directory=sharedir / "slurm_error1")

    # Check if the result has been processed correctly
    assert len(slurm_stats.results) == 9
    assert slurm_stats.results[0]

    slurm_stats.to_csv(str(tmpdir.join("test.csv")))
