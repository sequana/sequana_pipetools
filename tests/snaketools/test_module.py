from sequana_pipetools import snaketools, Module


def test_md5():
    m = Module("pipeline:fastqc")
    m.md5()


def test_modules():
    assert "cutadapt" in snaketools.modules.keys()
    assert snaketools.modules["cutadapt"].endswith("cutadapt.rules")


def test_module():
    # a rule without README
    m = snaketools.Module("cutadapt")
    m  # test __repr__
    m.__repr__()
    print(m)
    m.path
    m.snakefile
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
