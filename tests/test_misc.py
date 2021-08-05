from sequana_pipetools.misc import Colors, print_version, print_newest_version, error



def test_colors():

    c = Colors()
    msg = "test"
    c.failed(msg)
    c.bold(msg)
    c.purple(msg)
    c.fail(msg)
    c.error(msg)
    c.warning(msg)
    c.underlined(msg)
    c.blue(msg)
    c.green(msg)


def test_error():
    try:
        error("message", "rnaseq")
        assert False
    except:
        assert True


def test_print_version():
    try:
        print_version("quality_control")
    except:
        pass
    try:
        print_version("sequana_dummy")
    except:
        pass


def test_new_version():
    try:
        print_newest_version("quality_control")
        assert False
    except NotImplementedError:
        assert True
