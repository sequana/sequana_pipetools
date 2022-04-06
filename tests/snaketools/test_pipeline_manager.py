import os
import subprocess

import pytest

from sequana_pipetools import snaketools, SequanaConfig, Module
from sequana_pipetools.misc import PipetoolsException

from .. import test_dir


def test_pipeline_manager(tmpdir):
    # test missing input_directory
    cfg = SequanaConfig({})
    with pytest.raises(PipetoolsException):
        pm = snaketools.PipelineManager("custom", cfg)

    # normal behaviour but no input provided:
    config = Module("pipeline:fastqc")._get_config()
    cfg = SequanaConfig(config)
    with pytest.raises(ValueError):
        pm = snaketools.PipelineManager("custom", cfg)

    # normal behaviour
    cfg = SequanaConfig(config)
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    pm = snaketools.PipelineManager("custom", cfg)
    assert not pm.paired

    cfg = SequanaConfig(config)
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "Hm*gz"
    pm = snaketools.PipelineManager("custom", cfg)
    assert pm.paired

    pm.getwkdir("pipeline:fastqc")
    pm.getrawdata()
    pm.getname("pipeline:fastqc")

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
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "Hm*gz"
    pm = snaketools.pipeline_manager.PipelineManagerGeneric("fastqc", cfg)
    pm.getwkdir("fastqc")
    pm.getrawdata()
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
    try:
        pm.teardown()
    except Exception:
        assert False
    finally:
        os.remove("Makefile")

    multiqc = tmpdir.join('multiqc.html')
    with open(multiqc, 'w') as fh:
        fh.write("test")
    pm.clean_multiqc(multiqc)

    with pytest.raises(PipetoolsException):
        pm.error('test')

    # test attribute
    pm.snakefile

    # test summary
    pm.get_html_summary()

    # test the sample_func 
    cfg.config.input_pattern = "Hm*gz"
    def sample_func(filename):
        d = filename.replace("_001.fastq.gz", "")
        d = d.split('/')[-1]
        return d.split("_")[0]
    pm = snaketools.pipeline_manager.PipelineManagerGeneric("fastqc", cfg, sample_func=sample_func)
    assert list(pm.samples.keys()) == ['Hm2']

def test_pipeline_manager_wrong_inputs(tmpdir):

    # test wrong input files
    cfg = SequanaConfig({})
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "DUMMY*gz"
    with pytest.raises(ValueError):
        pm = snaketools.pipeline_manager.PipelineManagerGeneric("fastqc", cfg)
        pm.getrawdata()


    # test missing input_directory
    cfg = SequanaConfig({})
    #cfg.config.input_directory, cfg.config.input_pattern = 
    cfg.config.input_pattern = "DUMMY*gz"
    with pytest.raises(PipetoolsException):
        pm = snaketools.pipeline_manager.PipelineManager("fastqc", cfg)

    # test wrong  input_directory
    cfg = SequanaConfig({})
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_directory =  "DUMMY"
    with pytest.raises(PipetoolsException):
        pm = snaketools.pipeline_manager.PipelineManager("fastqc", cfg)


def test_directory():

    cfg = SequanaConfig({})
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "Hm*gz"
    pm = snaketools.pipeline_manager.PipelineManagerDirectory("test", cfg)

