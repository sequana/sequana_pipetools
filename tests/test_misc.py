from sequana_pipetools.misc import (
    Colors,
    download_and_extract_tar_gz,
    error,
    levenshtein_distance,
    print_version,
    url2hash,
)


def test_download_and_extract_tar_gz(tmpdir):

    url = "https://github.com/sequana/sequana_pipetools/archive/refs/tags/v1.0.3.tar.gz"
    download_and_extract_tar_gz(url, tmpdir)


def test_levenshtein():
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("flaw", "lawn") == 2


def test_url2hash():
    md5 = url2hash("https://zenodo.org/record/7822910/files/samtools_1.17_minimap2_2.24.0.img")
    assert md5 == "c3e4a8244ce7b65fa873ebda134fea7f"


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
