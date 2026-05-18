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

    try:
        ff = snaketools.FastQFactory("*dummy___not_possible", verbose=True, read_tag="")

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


def test_fastqfactory_get_file_methods():
    fastq = os.path.join(test_dir, "data", "Hm2*gz")
    ff = snaketools.FastQFactory(fastq, read_tag="R[12]")

    # Test get_file1 and get_file2 with explicit tag
    tag = ff.tags[0]
    file1 = ff.get_file1(tag)
    file2 = ff.get_file2(tag)
    assert file1 is not None
    assert file2 is not None
    assert file1 != file2

    # Test get_file1 and get_file2 with None tag (single sample case)
    file1_none = ff.get_file1(None)
    file2_none = ff.get_file2(None)
    assert file1_none == file1
    assert file2_none == file2


def test_fastqfactory_get_file_errors():
    fastq = os.path.join(test_dir, "data", "Hm2*gz")
    ff = snaketools.FastQFactory(fastq, read_tag="R[12]")

    # Test invalid tag
    with pytest.raises(ValueError, match="Invalid tag"):
        ff.get_file1("invalid_tag")

    # Test ambiguous tag with multiple samples
    # Create a FastQFactory with multiple samples to trigger ambiguous tag error
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple sample files
        for sample in ["A", "B"]:
            for r in [1, 2]:
                fname = os.path.join(tmpdir, f"sample.{sample}_R{r}_001.fastq.gz")
                with open(fname, "w") as f:
                    f.write("test")

        ff_multi = snaketools.FastQFactory(os.path.join(tmpdir, "*_R[12]_*.gz"), read_tag="_R[12]_")
        # With multiple samples, getting file without tag should raise
        with pytest.raises(ValueError, match="Ambiguous tag"):
            ff_multi.get_file1(None)


def test_fastqfactory_r2_missing():
    # Test case where R2 file is missing (returns None)
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create only R1 files (no R2)
        for sample in ["A", "B"]:
            fname = os.path.join(tmpdir, f"sample.{sample}_R1_001.fastq.gz")
            with open(fname, "w") as f:
                f.write("test")

        ff = snaketools.FastQFactory(os.path.join(tmpdir, "*_R[12]_*.gz"), read_tag="_R[12]_")
        # R2 should return None when missing
        tag = ff.tags[0]
        assert ff.get_file2(tag) is None
        # Data should not be paired when R2 is missing
        assert not ff.paired


def test_fastqfactory_readtag_none():
    # Test FastQFactory with read_tag=None (unpaired data)
    fastq = os.path.join(test_dir, "data", "Hm2*gz")
    ff = snaketools.FastQFactory(fastq, read_tag=None)

    assert ff.read_tag == ""
    assert not ff.paired
    # With empty read_tag, get_file1 should work with startswith matching
    tag = ff.tags[0]
    file1 = ff.get_file1(tag)
    assert file1 is not None


def test_fastqfactory_no_candidates():
    # Test error during FastQFactory init when no files match the read_tag
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files that don't match the read_tag pattern
        fname = os.path.join(tmpdir, "sample_001.fastq.gz")
        with open(fname, "w") as f:
            f.write("test")

        # This should raise ValueError during init because files don't match read_tag
        with pytest.raises(ValueError, match="No files found with the requested pattern"):
            snaketools.FastQFactory(os.path.join(tmpdir, "*.fastq.gz"), read_tag="_R[12]_")


def test_fastqfactory_too_many_candidates():
    # Test error when too many candidates found for a tag
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple R1 files that match the same tag
        for i in range(2):
            fname = os.path.join(tmpdir, f"sample_R1_00{i}.fastq.gz")
            with open(fname, "w") as f:
                f.write("test")

        ff = snaketools.FastQFactory(os.path.join(tmpdir, "*_R[12]_*.gz"), read_tag="_R[12]_")
        # This should raise ValueError because multiple candidates match
        with pytest.raises(ValueError, match="Found too many candidates"):
            ff.get_file1(ff.tags[0])


def test_fastqfactory_paired_mismatch():
    # Test case where R1 and R2 counts don't match (mixed paired/unpaired)
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 2 R1 files but only 1 R2 file
        for i in range(2):
            fname = os.path.join(tmpdir, f"sample{i}_R1_001.fastq.gz")
            with open(fname, "w") as f:
                f.write("test")
        fname = os.path.join(tmpdir, "sample0_R2_001.fastq.gz")
        with open(fname, "w") as f:
            f.write("test")

        # FastQFactory init succeeds, but accessing paired property should raise
        ff = snaketools.FastQFactory(os.path.join(tmpdir, "*_R[12]_*.gz"), read_tag="_R[12]_")
        # Accessing paired property should trigger the error
        with pytest.raises(SystemExit):
            _ = ff.paired


def test_fastqfactory_no_candidates_in_get_file():
    # Test error when _get_file finds no candidates
    # This is an edge case that occurs when the internal state is corrupted
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create proper R1/R2 files
        fname_r1 = os.path.join(tmpdir, "sample_R1_001.fastq.gz")
        fname_r2 = os.path.join(tmpdir, "sample_R2_001.fastq.gz")
        for fname in [fname_r1, fname_r2]:
            with open(fname, "w") as f:
                f.write("test")

        ff = snaketools.FastQFactory(os.path.join(tmpdir, "*_R[12]_*.gz"), read_tag="_R[12]_")
        # Manually remove the R1 file from _glob to simulate corrupted state
        ff._glob = [f for f in ff._glob if "R1" not in f]

        # Now trying to get_file1 should fail with Exception
        tag = ff.tags[0]
        with pytest.raises(Exception):
            ff.get_file1(tag)


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


def test_file_factory_paired_end_validation():
    # Test the new paired-end validation logic:
    # Allow unique_count * 2 == len(glob) for paired-end reads (e.g., R1/R2),
    # but raise for other cases of duplicate sample names.
    # The error case is already tested in test_file_factory_sample_names
    # with the "prefix.*.gz" pattern which should raise due to ambiguous names.
    # This test verifies the new logic doesn't break existing paired file handling.
    fastq = os.path.join(test_dir, "data", "Hm2*gz")
    ff = snaketools.FileFactory(fastq)
    # Should succeed with 2 files (paired-end case)
    assert len(ff) == 2
    assert len(ff.filenames) == 2
