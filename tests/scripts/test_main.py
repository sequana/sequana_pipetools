import sys
import pytest

from sequana_pipetools.scripts.completion import main



from click.testing import CliRunner




def test_main(monkeypatch):

    runner = CliRunner()
    results = runner.invoke(main, ['--help'])
    assert results.exit_code == 0

