import os
import sys
from unittest.mock import patch

from click.testing import CliRunner

from sequana_pipetools.scripts.main import main
from sequana_pipetools.scripts.monitor import main as monitor_main

from . import test_dir


def test_main():
    runner = CliRunner()
    results = runner.invoke(main, ["--help"])
    assert results.exit_code == 0


def test_version():
    runner = CliRunner()
    results = runner.invoke(main, ["--version"])
    assert results.exit_code == 0


def test_completion(monkeypatch):

    # FIXME
    # monkeypatch.setattr("builtins.input", lambda x: "y")
    # runner = CliRunner()
    # results = runner.invoke(main, ["--completion", "rnaseq"])
    # assert results.exit_code == 0

    runner = CliRunner()
    results = runner.invoke(main, ["--completion", "fastqc", "--overwrite"])
    assert results.exit_code == 0


def test_url2hash():
    runner = CliRunner()
    results = runner.invoke(main, ["--url2hash", "test"])
    assert results.exit_code == 0
    assert results.output == "098f6bcd4621d373cade4e832627b4f6\n"


def test_stats():
    runner = CliRunner()
    results = runner.invoke(main, ["--stats"])
    assert results.exit_code == 0


def test_config_to_schema():
    runner = CliRunner()
    results = runner.invoke(main, ["--config-to-schema", f"{test_dir}/data/config.yaml"])
    assert results.exit_code == 0


def test_slurm_diag():
    runner = CliRunner()
    results = runner.invoke(main, ["--slurm-diag"])
    assert results.exit_code == 0


def test_dot2png(tmpdir):
    runner = CliRunner()
    dotfile = os.path.join(test_dir, "..", "data", "test_dag.dot")
    results = runner.invoke(main, ["--dot2png", dotfile])
    assert results.exit_code == 0


def test_diagnose(tmp_path):
    runner = CliRunner()
    with patch("sequana_pipetools.diagnose.diagnose", return_value="All good.") as mock_diag:
        results = runner.invoke(main, ["--diagnose", "--workdir", str(tmp_path)])
    assert results.exit_code == 0
    assert "All good." in results.output
    mock_diag.assert_called_once_with(workdir=str(tmp_path), provider="mistral", model=None)


def test_diagnose_error(tmp_path):
    runner = CliRunner()
    with patch("sequana_pipetools.diagnose.diagnose", side_effect=EnvironmentError("no key")):
        results = runner.invoke(main, ["--diagnose", "--workdir", str(tmp_path)])
    assert results.exit_code == 1
    assert "no key" in results.output


def test_monitor_help():
    runner = CliRunner()
    results = runner.invoke(monitor_main, ["--help"])
    assert results.exit_code == 0
    assert "--snakefile" in results.output


def test_monitor_runs(tmp_path):
    runner = CliRunner()
    with patch("sequana_pipetools.monitor.run_monitor", return_value=0) as mock_run:
        results = runner.invoke(
            monitor_main,
            [
                "--snakefile",
                "pipeline.rules",
                "--profile",
                ".sequana/profile_local",
                "--name",
                "test",
                "--workdir",
                str(tmp_path),
            ],
        )
    assert results.exit_code == 0
    mock_run.assert_called_once_with("pipeline.rules", ".sequana/profile_local", "test", "", str(tmp_path))
