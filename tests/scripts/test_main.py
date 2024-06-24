import sys
import os

from click.testing import CliRunner

from sequana_pipetools.scripts.main import main

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
    results = runner.invoke(main, ["--completion", "fastqc", "--force"])
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


def test_dot2png():
    runner = CliRunner()
    dotfile = os.path.join(test_dir, "..", "data", "test_dag.dot")
    results = runner.invoke(main, ["--dot2png", dotfile])
    assert results.exit_code == 0


