import os

import pytest

from sequana_pipetools import snaketools, Module, SequanaConfig

from urllib.error import URLError

from .. import test_dir


def test_valid_config(tmpdir):
    config = SequanaConfig(None)

    s = Module("pipeline:fastqc")
    config = SequanaConfig(s.config)
    fh = tmpdir.join("config.yml")
    config.save(fh)


# this is a regression bug that guarantees that
# changing an attribute is reflected in the output config file
# when we change a value
def test_attrdict(tmpdir):
    s = Module("pipeline:fastqc")
    config = SequanaConfig(s.config)

    # This must be accessicle as an attribute
    config.config.general.method_choice

    # moreover, we should be able to changed it
    config.config.general.method_choice = "XXXX"

    # and save it . let us check that it was saved correcly
    fh = tmpdir.join("config.yml")

    config.save(fh)

    # by reading it back
    config2 = SequanaConfig(str(fh))
    assert config2.config.general.method_choice == "XXXX"



def test_sequana_config(tmpdir):
    s = Module("pipeline:fastqc")
    config = SequanaConfig(s.config)

    assert config.config.get("input_pattern") == "*fastq.gz"
    assert config.config.get("kraken:dummy") is None

    # --------------------------------- tests different constructors
    config = SequanaConfig()
    config = SequanaConfig({"test": 1})
    assert config.config.test == 1

    # with a dictionary
    config = SequanaConfig(config.config)

    # with a sequanaConfig instance
    config = SequanaConfig(config)

    # with a non-existing file
    with pytest.raises(FileNotFoundError):
        config = SequanaConfig("dummy_dummy")

    # Test warning
    s = Module("pipeline:fastqc")
    config = SequanaConfig(s.config)
    config._recursive_update(config._yaml_code, {"input_directory_dummy": "test"})

    # config.check_config_with_schema(s.schema_config)
    # loop over all pipelines, read the config, save it and check the content is
    # identical. This requires to remove the templates. We want to make sure the
    # empty strings are kept and that "no value" are kept as well
    #
    #    field1: ""
    #    field2:
    #
    # is unchanged

    # test all installed pipelines saving/reading config file
    output = tmpdir.join("test.yml")
    for pipeline in snaketools.pipeline_names:
        config_filename = Module(pipeline)._get_config()
        cfg1 = SequanaConfig(config_filename)

        cfg1.save(output)
        cfg2 = SequanaConfig(str(output))
        assert cfg2._yaml_code == cfg1._yaml_code
        assert cfg1.config == cfg2.config

    # test config with a _directory or _file  based on the fastqc pipeline
    cfg = SequanaConfig(s.config)
    cfg.config.input_directory = "~/"
    cfg.config.multiqc.config_file = "~/"
    cfg._recursive_cleanup(cfg.config) 
    assert cfg.config.input_directory.startswith("/")
    assert cfg.config.multiqc.config_file.startswith("/")


def test_check_config_with_schema():
    schema = Module("pipeline:fastqc").schema_config
    SequanaConfig(Module("pipeline:fastqc").config).check_config_with_schema(schema)


def test_check_bad_config_with_schema():
    cfg_name = os.path.join(test_dir, "data", "config.yml")
    schema = os.path.join(test_dir, "data", "schema.yml")

    cfg = SequanaConfig(cfg_name)
    # threads can not be a string
    cfg.config["busco"]["threads"] = ""
    assert not cfg.check_config_with_schema(schema)


def test_check_config_with_schema_and_ext(tmpdir):
    cfg_name = os.path.join(test_dir, "data", "config.yml")
    schema = os.path.join(test_dir, "data", "schema.yml")

    cfg = SequanaConfig(cfg_name)
    assert cfg.check_config_with_schema(schema)

    # not nullable key cannot be empty
    cfg.config["busco"]["lineage"] = ""
    assert not cfg.check_config_with_schema(schema)

    # but it is not a problem the rule is not necessary
    cfg.config["busco"]["do"] = False
    assert cfg.check_config_with_schema(schema)

    cfg.config["busco"].update({"do": True, "lineage": "bacteria", "threads": ""})
    assert not cfg.check_config_with_schema(schema)
