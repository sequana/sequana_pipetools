import sys

import pytest
from click.testing import CliRunner

from sequana_pipetools.scripts.main import main


def test_main():
    runner = CliRunner()
    results = runner.invoke(main, ["--help"])
    assert results.exit_code == 0


def test_version():
    runner = CliRunner()
    results = runner.invoke(main, ["--version"])
    assert results.exit_code == 0


def test_completion(monkeypatch):

    monkeypatch.setattr("builtins.input", lambda x: "y")
    runner = CliRunner()
    results = runner.invoke(main, ["--completion", "rnaseq"])
    assert results.exit_code == 0

    runner = CliRunner()
    results = runner.invoke(main, ["--completion", "fastqc", "--force"])
    assert results.exit_code == 0
