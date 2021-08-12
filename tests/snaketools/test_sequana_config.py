import os

import pytest

from sequana_pipetools import snaketools, Module, SequanaConfig

from .. import test_dir


def test_valid_config(tmpdir):
    config = SequanaConfig(None)

    s = Module("fastqc")
    config = SequanaConfig(s.config)
    fh = tmpdir.join("config.yml")
    config.save(fh)


def test_sequana_config(tmpdir):
    s = Module("fastqc")
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
    # with a non-yaml file
    json = os.path.join(test_dir, "data", "test_summary_fastq_stats.json")
    config = SequanaConfig(json)
    with pytest.raises(FileNotFoundError):
        config = SequanaConfig("dummy_dummy")

    # Test an exception
    s = Module("fastqc")
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

    output = tmpdir.join("test.yml")
    for pipeline in snaketools.pipeline_names:
        config_filename = Module(pipeline)._get_config()
        cfg1 = SequanaConfig(config_filename)
        cfg1.cleanup()  # remove templates and strip strings

        cfg1.save(output)
        cfg2 = SequanaConfig(str(output))
        assert cfg2._yaml_code == cfg1._yaml_code
        cfg2._update_config()
        assert cfg1.config == cfg2.config


def test_copy_requirements(tmpdir):
    # We need 4 cases:
    # 1- http
    # 2- a sequana file (phix)
    # 3- an existing file elsewhere (here just a temporary file)
    # 4- an existing file in the same directory as the target dir

    # Case 3: a temporary file
    tmp_require = tmpdir.join("requirement.txt")

    # Case 4: a local file (copy of the temp file)
    # TODO
    # localfile = temprequire.name.split(os.sep)[-1]
    # shutil.copy(temprequire.name, targetdir)

    cfg = SequanaConfig()
    cfg.config.requirements = [
        "phiX174.fa",
        str(tmp_require),
        # localfile,
        "https://raw.githubusercontent.com/sequana/sequana/master/README.rst",
    ]
    cfg._update_yaml()
    cfg.copy_requirements(target=str(tmpdir))

    # error
    cfg.config.requirements = ["dummy"]
    cfg.copy_requirements(target=str(tmpdir))


def test_check_config_with_schema():
    schema = Module("fastqc").schema_config
    SequanaConfig(Module("fastqc").config).check_config_with_schema(schema)


def test_check_bad_config_with_schema():
    cfg_name = os.path.join(test_dir, "data", "config.yml")
    schema = os.path.join(test_dir, "data", "schema.yml")

    cfg = SequanaConfig(cfg_name)
    # threads can not be a string
    cfg.config["busco"]["threads"] = ""
    cfg._update_yaml()
    assert not cfg.check_config_with_schema(schema)


def test_check_config_with_schema_and_ext(tmpdir):
    cfg_name = os.path.join(test_dir, "data", "config.yml")
    schema = os.path.join(test_dir, "data", "schema.yml")

    cfg = SequanaConfig(cfg_name)
    assert cfg.check_config_with_schema(schema)

    # not nullable key cannot be empty
    cfg.config["busco"]["lineage"] = ""
    cfg._update_yaml()
    assert not cfg.check_config_with_schema(schema)

    # but it is not a problem the rule is not necessary
    cfg.config["busco"]["do"] = False
    cfg._update_yaml()
    assert cfg.check_config_with_schema(schema)

    cfg.config["busco"].update({"do": True, "lineage": "bacteria", "threads": ""})
    cfg._update_yaml()
    assert not cfg.check_config_with_schema(schema)
