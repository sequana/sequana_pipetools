import os

import pytest

from sequana_pipetools import snaketools
from sequana_pipetools.misc import PipetoolsException

from .. import test_dir


def test_file_name_factory():
    import glob

    def inner_test(ff):
        len(ff)
        print(ff)
        ff.filenames
        ff.realpaths
        ff.all_extensions
        ff.extensions

    # list
    list_files = glob.glob("*.*")
    ff = snaketools.FileFactory(list_files)
    inner_test(ff)

    # glob
    ff = snaketools.FileFactory("*.*")
    inner_test(ff)

    ff = snaketools.FastQFactory(test_dir + "/data/Hm2*fastq.gz", verbose=True)
    assert ff.tags == ["Hm2_GTGAAA_L005"]

    ff.get_file1(ff.tags[0])
    ff.get_file2(ff.tags[0])
    assert len(ff) == 1

    try:
        ff = snaketools.FastQFactory(test_dir + "/data/Hm2*fastq.gz", verbose=True, read_tag="dummy[12]")
        assert False
    except ValueError:
        assert True


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


def test_file_factory_sample_names():

    # prefix.mess.A.fastq.gz
    # prefix.mess.B.fastq.gz
    #
    # should return A and B easily
    ff = snaketools.FileFactory(test_dir + "/data/prefix.mess.*")
    assert set(ff.filenames) == {"A", "B"}

    # prefix.A.fastq.gz and prefix.mess.A.fastq.gz
    # should return mess and A because they do not have
    # the same structure. In simple cases it should work out of the box
    ff = snaketools.FileFactory(test_dir + "/data/prefix.*A.*")
    assert set(ff.filenames) == {"mess", "A"}

    # but in more complex cases,
    # prefix.mess.A.fastq.gz
    # prefix.mess.A.fastq.gz
    # prefix.A.fastq.gz
    # prefix.B.fastq.gz
    #
    # we remov prefix but remaining part are but
    # not unique. Therefore an error is raised.
    with pytest.raises(PipetoolsException):
        ff = snaketools.FileFactory(test_dir + "/data/prefix.*.gz")
        ff.filenames

    # This cannot be solved. But removing a non unique prefix is possible
    # using a list of prefixes to remove.
    ff = snaketools.FileFactory(test_dir + "/data/prefix2*gz", extra_prefixes_to_strip=["prefix2.", "mess."])
    assert set(ff.filenames) == {"A", "C", "B"}

    # special case of a single file should not remove the prefix.
    ff = snaketools.FileFactory(test_dir + "/data/prefix.A.fastq.gz")
    assert set(ff.filenames) == {"prefix"}

    # finally, we can also use a sample_pattern
    ff = snaketools.FileFactory(test_dir + "/data/prefix.mess.*", sample_pattern="prefix.mess.{sample}.fastq.gz")
    assert set(ff.filenames) == {"A", "B"}
