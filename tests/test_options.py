from sequana_pipetools.options import *
from easydev import AttrDict
import argparse


def test_misc():

    import sys
    sys.argv.append("--version")
    from sequana_pipetools.options import init_pipeline
    try:
        init_pipeline("fastqc")
    except:
        pass
    sys.argv.remove("--version")
    sys.argv.append("--deps")
    try:
        init_pipeline("fastqc")
    except:
        pass


def test_feature_counts():
    p = argparse.ArgumentParser()
    so = FeatureCountsOptions()
    so.add_options(p)


def test_trimming_options():

    p = argparse.ArgumentParser()
    so = TrimmingOptions()
    so.add_options(p)
    p.parse_args(["--trimming-quality", "40"])
    try:
        p.parse_args(["--trimming-quality", "-40"])
    except:
        argparse.ArgumentTypeError



def test_snakemake_options():
    from sequana_pipetools.options import SnakemakeOptions
    p = argparse.ArgumentParser()
    so = SnakemakeOptions()
    so._default_jobs() #test sheduler
    so.add_options(p)
    p.parse_args([])



def test_krakenl_options():
    from sequana_pipetools.options import KrakenOptions
    p = argparse.ArgumentParser()
    so = KrakenOptions()
    so.add_options(p)
    p.parse_args([])


def test_slurm_options():
    from sequana_pipetools.options import SlurmOptions
    p = argparse.ArgumentParser()
    so = SlurmOptions()
    so.add_options(p)
    p.parse_args([])


def test_input_options():
    from sequana_pipetools.options import InputOptions
    p = argparse.ArgumentParser()
    so = InputOptions()
    so.add_options(p)
    p.parse_args([])


def test_general_options():
    from sequana_pipetools.options import GeneralOptions
    p = argparse.ArgumentParser()
    so = GeneralOptions()
    so.add_options(p)
    p.parse_args([])
