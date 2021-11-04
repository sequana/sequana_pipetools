from sequana_pipetools import snaketools, Module


def test_md5():
    m = Module("pipeline:fastqc")
    m.md5()


def test_modules():
    assert "dag" in snaketools.modules.keys()
    assert snaketools.modules["dag"].endswith("dag.rules")


def test_module():
    # a rule without README
    m = snaketools.Module("fastp")
    m.description
    m  # test __repr__
    m.__repr__()
    m.path
    m.snakefile
    m.overview
    # a rule with README
    m = snaketools.Module("dag")
    m.description
    m.overview
    assert m.is_executable()
    m.check()

    # a pipeline
    m = snaketools.Module("pipeline:fastqc")
    m.is_executable()
    m.check()
    m.snakefile
    m.name
    assert m.schema_config.endswith("schema.yaml")


def test_module_version():
    Module("snpeff/1.0").version == "1.0"
