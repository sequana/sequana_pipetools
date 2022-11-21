import sys
import pytest

from sequana_pipetools.scripts.completion import main
from sequana_pipetools.scripts.completion import Complete


def test_complete():
    c = Complete("fastqc")
    c.save_completion_script()


def test_main(monkeypatch):
    sys.argv = ["dummy", "--name", "fastqc"]
    monkeypatch.setattr("builtins.input", lambda x: 'y')
    main()

    sys.argv = ["dummy", "--name", "fastqc", "--force"]
    main()

    sys.argv = ["dummy", "--help"]
    with pytest.raises(SystemExit):
        main()

    sys.argv = ["dummy"]
    with pytest.raises(SystemExit):
        main()

    sys.argv = ["dummy", "--name", "all"]
    monkeypatch.setattr("builtins.input", lambda x: 'y')
    main()
