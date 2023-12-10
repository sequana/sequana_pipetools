from sequana_pipetools import Pipeline, snaketools


def test_module():

    # a pipeline
    m = snaketools.Pipeline("fastqc")
    m.md5()
    m.is_executable()
    m.check()
    m.snakefile
    m.name
    assert m.schema_config.endswith("schema.yaml")

    print(m)
    m
    m.version
    m.__repr__()
