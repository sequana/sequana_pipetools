from sequana_pipetools.completion import Complete
from mock import patch


def test_complete():
    c = Complete("fastqc")
    c.save_completion_script()


def test_main(monkeypatch):
    from sequana_pipetools.completion import main
    import sys
    sys.argv = ["dummy", "--name", "fastqc"]
    monkeypatch.setattr("builtins.input", lambda x: 'y')
    main()

    sys.argv = ["dummy", "--name", "fastqc", "--force"]
    main()


    sys.argv = ["dummy", "--help"]
    try:
        main()
        assert False
    except:
        assert True

    sys.argv = ["dummy"]
    try:
        main()
        assert False
    except:
        assert True

    sys.argv = ["dummy", "--name", "all"]
    monkeypatch.setattr("builtins.input", lambda x: 'y')
    main()
