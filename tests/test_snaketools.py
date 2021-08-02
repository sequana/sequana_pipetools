import os
import subprocess
import tempfile
import pytest

from sequana_pipetools import snaketools
from sequana_pipetools.snaketools import DOTParser
from sequana_pipetools import Module, SequanaConfig

from . import test_dir


DATA_DIR = os.sep.join((test_dir, "data"))


def test_dot_parser():
    s = DOTParser(os.sep.join((DATA_DIR, "test_dag.dot")))
    s.add_urls(mapper={"bwa_fix": "test.html"})
    try:
        os.remove("test_dag.ann.dot")
    except FileNotFoundError:
        pass

    s.mode = "v1"
    s.add_urls(mapper={"bwa_fix": "test.html"})
    try:
        os.remove("test_dag.ann.dot")
    except FileNotFoundError:
        pass


def test_md5():
    m = Module("fastqc")
    m.md5()


def test_modules():
    assert "dag" in snaketools.modules.keys()
    assert snaketools.modules["dag"].endswith("dag.rules")


def test_module():
    # a rule without README
    m = snaketools.Module("mark_duplicates_dynamic")
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
    m = snaketools.Module("fastqc")
    m.is_executable()
    m.check()
    m.snakefile
    m.name
    assert m.schema_config.endswith("schema.yaml")


def test_valid_config():
    config = snaketools.SequanaConfig(None)

    s = snaketools.Module("fastqc")
    config = snaketools.SequanaConfig(s.config)

    from easydev import TempFile

    with TempFile() as fh:
        config.save(fh.name)


def test_sequana_config(tmpdir):
    s = snaketools.Module("fastqc")
    config = snaketools.SequanaConfig(s.config)

    assert config.config.get("input_pattern") == "*fastq.gz"
    assert config.config.get("kraken:dummy") is None

    # --------------------------------- tests different constructors
    config = snaketools.SequanaConfig()
    config = snaketools.SequanaConfig({"test": 1})
    assert config.config.test == 1
    # with a dictionary
    config = snaketools.SequanaConfig(config.config)
    # with a sequanaConfig instance
    config = snaketools.SequanaConfig(config)
    # with a non-yaml file
    json = os.sep.join((DATA_DIR, "test_summary_fastq_stats.json"))
    config = snaketools.SequanaConfig(json)
    with pytest.raises(FileNotFoundError):
        config = snaketools.SequanaConfig("dummy_dummy")

    # Test an exception
    s = snaketools.Module("fastqc")
    config = snaketools.SequanaConfig(s.config)
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


def test_check_config_with_schema():
    schema = Module("fastqc").schema_config
    SequanaConfig(Module("fastqc").config).check_config_with_schema(schema)


def test_module_version():
    Module("snpeff/1.0").version == "1.0"


def test_message():
    snaketools.message("test")


def test_pipeline_manager(tmpdir):
    # test missing input_directory
    cfg = SequanaConfig({})
    with pytest.raises(KeyError):
        pm = snaketools.PipelineManager("custom", cfg)

    # normal behaviour but no input provided:
    config = Module("fastqc")._get_config()
    cfg = SequanaConfig(config)
    cfg.cleanup()  # remove templates
    with pytest.raises(ValueError):
        pm = snaketools.PipelineManager("custom", cfg)

    # normal behaviour
    cfg = SequanaConfig(config)
    cfg.cleanup()  # remove templates
    file1 = os.sep.join((DATA_DIR, "Hm2_GTGAAA_L005_R1_001.fastq.gz"))
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    pm = snaketools.PipelineManager("custom", cfg)
    assert not pm.paired

    cfg = SequanaConfig(config)
    cfg.cleanup()  # remove templates
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "Hm*gz"
    pm = snaketools.PipelineManager("custom", cfg)
    pm.plot_stats()
    assert pm.paired

    pm.getlogdir("fastqc")
    pm.getwkdir("fastqc")
    pm.getrawdata()
    pm.getreportdir("test")
    pm.getname("fastqc")

    # Test different configuration of input_directory, input_readtag,
    # input_pattern
    # Test the _R[12]_ paired
    working_dir = tmpdir.mkdir('test_Rtag_pe')
    cfg = SequanaConfig()
    cfgname = working_dir / "config.yaml"
    cfg.config.input_pattern = "*fastq.gz"
    cfg.config.input_directory = str(working_dir)
    cfg.config.input_readtag = "_R[12]_"
    cfg._update_yaml()
    cfg.save(cfgname)
    cmd = f"touch {working_dir}/test_R1_.fastq.gz"
    subprocess.call(cmd.split())
    cmd = f"touch {working_dir}/test_R2_.fastq.gz"
    subprocess.call(cmd.split())
    pm = snaketools.PipelineManager("test", str(cfgname))
    assert pm.paired

    # Test the _[12]. paired
    working_dir = tmpdir.mkdir('test_tag_pe')
    cfg = SequanaConfig()
    cfgname = working_dir / "config.yaml"
    cfg.config.input_pattern = "*fastq.gz"
    cfg.config.input_directory = str(working_dir)
    cfg.config.input_readtag = "_[12]."
    cfg._update_yaml()
    cfg.save(cfgname)
    cmd = f"touch {working_dir}/test_1.fastq.gz"
    subprocess.call(cmd.split())
    cmd = f"touch {working_dir}/test_2.fastq.gz"
    subprocess.call(cmd.split())
    pm = snaketools.PipelineManager("test", str(cfgname))
    assert pm.paired

    # Test the _R[12]_ single end
    working_dir = tmpdir.mkdir('test_Rtag_se')
    cfg = SequanaConfig()
    cfgname = working_dir / "config.yaml"
    cfg.config.input_pattern = "*fastq.gz"
    cfg.config.input_directory = str(working_dir)
    cfg.config.input_readtag = "_R[12]_"
    cfg._update_yaml()
    cfg.save(cfgname)
    cmd = f"touch {working_dir}/test_R1_.fastq.gz"
    subprocess.call(cmd.split())
    pm = snaketools.PipelineManager("test", str(cfgname))
    assert not pm.paired

    # Test the _R[12]_ single end
    working_dir = tmpdir.mkdir('test_tag_se')
    cfg = SequanaConfig()
    cfgname = working_dir / "config.yaml"
    cfg.config.input_pattern = "*fq.gz"  # wrong on purpose
    cfg.config.input_directory = str(working_dir)
    cfg.config.input_readtag = "_R[12]_"
    cfg._update_yaml()
    cfg.save(cfgname)
    cmd = f"touch {working_dir}/test_R1_.fastq.gz"
    subprocess.call(cmd.split())
    try:
        pm = snaketools.PipelineManager("test", str(cfgname))
    except ValueError:
        assert True


def test_pipeline_manager_generic(tmpdir):
    cfg = SequanaConfig({})
    file1 = os.sep.join((DATA_DIR, "Hm2_GTGAAA_L005_R1_001.fastq.gz"))
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "Hm*gz"
    pm = snaketools.pipeline_manager.PipelineManagerGeneric("quality_control", cfg)
    pm.getlogdir("fastqc")
    pm.getwkdir("fastqc")
    pm.getrawdata()
    pm.getreportdir("test")
    pm.getname("fastqc")
    gg = globals()
    gg["__snakefile__"] = "dummy"
    pm.setup(gg)
    del gg["__snakefile__"]

    class WF:
        included_stack = ["dummy", "dummy"]

    wf = WF()
    gg["workflow"] = wf
    pm.setup(gg)
    pm.teardown()

    multiqc = tmpdir.join('multiqc.html')
    with open(multiqc, 'w') as fh:
        fh.write("test")
    pm.clean_multiqc(multiqc)


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

    ff = snaketools.FastQFactory(DATA_DIR + "/Hm2*fastq.gz", verbose=True)
    assert ff.tags == ["Hm2_GTGAAA_L005"]

    ff.get_file1(ff.tags[0])
    ff.get_file2(ff.tags[0])
    assert len(ff) == 1


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

    cfg = snaketools.SequanaConfig()
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


def test_onsuccess(tmpdir):
    directory = tmpdir.mkdir("onsuccess")
    p1 = directory.join("Makefile")
    p2 = directory.join("cleanup.py")
    onsuc = snaketools.OnSuccess()
    onsuc.makefile_filename = p1
    onsuc.makefile_cleanup = p2


def test_onsuccess_cleaner():
    fh = tempfile.TemporaryDirectory()
    onsucc = snaketools.OnSuccessCleaner()
    onsucc.makefile_filename = fh.name + os.sep + "Makefile"
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


def test_fastqfactory():
    with pytest.raises(ValueError):
        snaketools.FastQFactory("*", read_tag="error")
    with pytest.raises(ValueError):
        snaketools.FastQFactory("*", read_tag="[12]")

    ff = snaketools.FastQFactory(DATA_DIR + os.sep + "Hm2*gz", read_tag="R[12]")
    assert ff.paired
    assert ff.tags == ["Hm2_GTGAAA_L005_"]

    ff = snaketools.FastQFactory(DATA_DIR + os.sep + "Hm2*gz", read_tag=None)
    assert not ff.paired
    assert sorted(ff.tags) == sorted(["Hm2_GTGAAA_L005_R2_001", "Hm2_GTGAAA_L005_R1_001"])


def test_makefile(tmpdir):
    mk = snaketools.Makefile()
    mk.makefile_filename = tmpdir.join("Makefile")
    mk.add_remove_done()
    mk.add_bundle()
    mk.save()


def test_bundle(tmpdir):
    os = snaketools.OnSuccess()
    os.makefile_filename = tmpdir.join("Makefile")
    os.cleanup_filename = tmpdir.join("sequana_cleanup.py")
    os.add_makefile()
    os.create_recursive_cleanup()
