import sys
import pytest

from sequana_pipetools.scripts.completion import main
from sequana_pipetools.scripts.completion import Complete



from click.testing import CliRunner


def test_complete():
    c = Complete("rnaseq")
    c.save_completion_script()


def test_main(monkeypatch):

    monkeypatch.setattr("builtins.input", lambda x: 'y')
    runner = CliRunner()
    results = runner.invoke(main, ['--name', "rnaseq"])
    assert results.exit_code == 0

    runner = CliRunner()
    results = runner.invoke(main, ['--name', "rnaseq", "--force"])
    assert results.exit_code == 0

    runner = CliRunner()
    results = runner.invoke(main, ['--help'])
    assert results.exit_code == 0

