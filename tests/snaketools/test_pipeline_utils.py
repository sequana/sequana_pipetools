import pytest

from sequana_pipetools.snaketools.pipeline_utils import (
    Makefile,
    OnSuccessCleaner,
    get_pipeline_statistics,
    message,
)


def test_message():
    message("test")


def test_onsuccess_cleaner(tmpdir):
    directory = tmpdir.mkdir("onsuccess")
    p1 = directory.join("Makefile")
    onsucc = OnSuccessCleaner()
    onsucc.makefile_filename = str(p1)
    onsucc.add_bundle()
    onsucc.add_makefile()


def test_get_pipeline_statistics():
    get_pipeline_statistics()


def test_makefile(tmpdir):
    mk = Makefile()
    mk.makefile_filename = tmpdir.join("Makefile")
    mk.add_remove_done()
    mk.add_bundle()
    mk.add_clean()
    mk.save()

    with pytest.raises(SystemExit):
        Makefile(sections=["dummy"])


def test_bundle(tmpdir):
    on_success = OnSuccessCleaner(outdir=str(tmpdir))
    on_success.makefile_filename = str(tmpdir.join("Makefile"))
    on_success.cleanup_filename = str(tmpdir.join("sequana_cleanup.py"))
    on_success.add_makefile()
