from sequana_pipetools.completion import Complete
from mock import patch

def test_complete():
    c = Complete("rnaseq")
    c.save_completion_script()


def test_main(monkeypatch):
    from sequana_pipetools.completion import main
    import sys
    sys.argv = ["dummy", "--name", "rnaseq"]
    monkeypatch.setattr("builtins.input", lambda x: 'y')
    main()

    sys.argv = ["dummy", "--name", "rnaseq", "--force"]
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
