import os

import pytest

from sequana_pipetools import snaketools

from .. import test_dir


def test_file_name_factory():
    import glob

    def inner_test(ff):
        len(ff)
        print(ff)
        ff.filenames
        ff.realpaths
        ff.all_extensions
        ff.pathnames
        ff.pathname
        ff.extensions

    # list
    list_files = glob.glob("*.py")
    ff = snaketools.FileFactory(list_files)
    inner_test(ff)

    # glob
    ff = snaketools.FileFactory("*py")
    inner_test(ff)

    ff = snaketools.FastQFactory(test_dir + "/data/Hm2*fastq.gz", verbose=True)
    assert ff.tags == ["Hm2_GTGAAA_L005"]

    ff.get_file1(ff.tags[0])
    ff.get_file2(ff.tags[0])
    assert len(ff) == 1


def test_fastqfactory():
    with pytest.raises(ValueError):
        snaketools.FastQFactory("*", read_tag="error")
    with pytest.raises(ValueError):
        snaketools.FastQFactory("*", read_tag="[12]")

    fastq = os.path.join(test_dir, "data", "Hm2*gz")
    ff = snaketools.FastQFactory(fastq, read_tag="R[12]")
    assert ff.paired
    assert ff.tags == ["Hm2_GTGAAA_L005_"]

    ff = snaketools.FastQFactory(fastq, read_tag=None)
    assert not ff.paired
    assert sorted(ff.tags) == sorted(["Hm2_GTGAAA_L005_R2_001", "Hm2_GTGAAA_L005_R1_001"])