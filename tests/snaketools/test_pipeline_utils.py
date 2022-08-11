from sequana_pipetools import snaketools


def test_message():
    snaketools.message("test")


def test_onsuccess_cleaner(tmpdir):
    directory = tmpdir.mkdir("onsuccess")
    p1 = directory.join("Makefile")
    onsucc = snaketools.OnSuccessCleaner()
    onsucc.makefile_filename = str(p1)
    onsucc.add_bundle()
    onsucc.add_makefile()


def test_build_dynamic_rule(tmpdir):

    code = "whatever"
    directory = str(tmpdir)
    snaketools.build_dynamic_rule(code, directory)


def test_get_pipeline_statistics():
    snaketools.get_pipeline_statistics()


def test_create_cleanup(tmpdir):
    snaketools.create_cleanup(tmpdir)


def test_makefile(tmpdir):
    mk = snaketools.Makefile()
    mk.makefile_filename = tmpdir.join("Makefile")
    mk.add_remove_done()
    mk.add_bundle()
    mk.save()


def test_bundle(tmpdir):
    on_success = snaketools.OnSuccessCleaner(outdir=str(tmpdir))
    on_success.makefile_filename = str(tmpdir.join("Makefile"))
    on_success.cleanup_filename = str(tmpdir.join("sequana_cleanup.py"))
    on_success.add_makefile()
