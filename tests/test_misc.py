from sequana_pipetools.misc import Colors, print_version, error, url2hash, levenshtein_distance



def test_levenshtein():
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("flaw", "lawn") == 2


def test_url2hash():
    md5 = url2hash("https://zenodo.org/record/7822910/files/samtools_1.17_minimap2_2.24.0.img")
    assert md5 == 'c3e4a8244ce7b65fa873ebda134fea7f'


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
        error("message", "fastqc")
        assert False
    except:
        assert True


def test_print_version():
    try:
        print_version("fastqc")
    except:
        pass
    try:
        print_version("sequana_dummy")
    except:
        pass
