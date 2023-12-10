import os
import subprocess
from pathlib import Path

import pytest

from sequana_pipetools import Pipeline, SequanaConfig, snaketools
from sequana_pipetools.misc import PipetoolsException

from .. import test_dir


def test_pipeline_manager(tmpdir):
    # test missing input_directory
    cfg = SequanaConfig({})
    with pytest.raises(PipetoolsException):
        pm = snaketools.PipelineManager("custom", cfg)

    # normal behaviour but no input provided:
    config = Pipeline("fastqc")._get_config()
    cfg = SequanaConfig(config)
    with pytest.raises(PipetoolsException):
        pm = snaketools.PipelineManager("custom", cfg)

    # normal behaviour
    cfg = SequanaConfig(config)
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    pm = snaketools.PipelineManager("custom", cfg)
    assert not pm.paired
    pm.teardown()

    # here not readtag provided, so data is considered to be non-fastq related
    # or at least not paired
    cfg = SequanaConfig(config)
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "Hm*gz"
    pm = snaketools.PipelineManager("custom", cfg)
    assert not pm.paired

    # Test different configuration of input_directory, input_readtag,
    # input_pattern
    # Test the _R[12]_ paired
    working_dir = tmpdir.mkdir("test_Rtag_pe")
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
    working_dir = tmpdir.mkdir("test_tag_pe")
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
    working_dir = tmpdir.mkdir("test_Rtag_se")
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
    working_dir = tmpdir.mkdir("test_tag_se")
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


def test_pipeline_manager_mixed_of_files(tmpdir):
    # Test a mix of bam and fastq files (with no tags)
    cfg = SequanaConfig({})
    cfg.config.input_directory = test_dir + os.sep + "data"
    cfg.config.input_pattern = "*notag*"
    pm = snaketools.PipelineManager("test", cfg)
    assert len(pm.samples) == 2
    assert not pm.paired

    # just test the attribute
    pm.snakefile

    pm.name = "fastqc"
    pm.get_html_summary()


def test_pipeline_manager_sample_func(tmpdir):
    cfg = SequanaConfig({})
    cfg.config.input_directory = test_dir + os.sep + "data"
    cfg.config.input_pattern = "Hm*.gz"

    def func(filename):
        return filename.split("/")[-1].split(".", 1)[0]

    pm = snaketools.PipelineManager("test", cfg, sample_func=func)

    # here, note that the sample_func is too simple and will extract the first part of the filename
    # so demultiplex.bc1010.fsatq.gz returns 'demultiplex'
    assert "Hm2_GTGAAA_L005_R1_001" in pm.samples
    assert "Hm2_GTGAAA_L005_R2_001" in pm.samples


def test_pipeline_manager_common_prefix():
    cfg = SequanaConfig({})
    cfg.config.input_directory = str(Path(test_dir) / "data")
    cfg.config.input_pattern = "prefix2*gz"
    pm = snaketools.PipelineManager("custom", cfg)
    assert "A" in pm.samples
    assert "B" in pm.samples
    assert "mess" in pm.samples
    pm = snaketools.PipelineManager("custom", cfg, prefixes_to_strip=["mess."])


def test_multiqc_clean(tmpdir):
    working_dir = tmpdir.mkdir("multiqc")
    cfg = SequanaConfig({})
    cfg.config.input_directory = str(Path(test_dir) / "data")
    cfg.config.input_pattern = "*notag*"
    pm = snaketools.PipelineManager("test", cfg)

    with open(working_dir / "multiqc.html", "w") as fout:
        fout.write('<a href="http://multiqc.info" target="_blank">"\ntest\ntest\ncode')
    pm.clean_multiqc(working_dir / "multiqc.html")
    pm.teardown(outdir=working_dir)
    pm.onerror()


def test_pipeline_manager_wrong_inputs(tmpdir):

    # test wrong input files
    cfg = SequanaConfig({})
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "DUMMY*gz"
    with pytest.raises(PipetoolsException):
        pm = snaketools.pipeline_manager.PipelineManager("fastqc", cfg)
        pm.getrawdata()

    # test missing input_directory
    cfg = SequanaConfig({})
    # cfg.config.input_directory, cfg.config.input_pattern =
    cfg.config.input_pattern = "DUMMY*gz"
    with pytest.raises(PipetoolsException):
        pm = snaketools.pipeline_manager.PipelineManager("fastqc", cfg)

    # test wrong  input_directory
    cfg = SequanaConfig({})
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_directory = "DUMMY"
    with pytest.raises(PipetoolsException):
        pm = snaketools.pipeline_manager.PipelineManager("fastqc", cfg)


def test_directory():

    cfg = SequanaConfig({})
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "Hm*gz"
    pm = snaketools.pipeline_manager.PipelineManagerDirectory("test", cfg)


def test_pipeline_others():
    cfg = SequanaConfig({})
    file1 = os.path.join(test_dir, "data", "Hm2_GTGAAA_L005_R1_001.fastq.gz")
    cfg.config.input_directory, cfg.config.input_pattern = os.path.split(file1)
    cfg.config.input_pattern = "Hm*gz"
    pm = snaketools.pipeline_manager.PipelineManager("fastqc", cfg)
    pm.getmetadata()
