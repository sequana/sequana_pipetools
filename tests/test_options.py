import argparse
import pytest
import sys
from sequana_pipetools.options import (
    before_pipeline,
    TrimmingOptions,
    SnakemakeOptions,
    KrakenOptions,
    FeatureCountsOptions,
    ClickGeneralOptions,
)

# for test_click_general_options() to work we need to define a global variable
NAME = "TEST"

def test_misc():

    sys.argv.append("--version")

    with pytest.raises(SystemExit):
        before_pipeline("fastqc")
    sys.argv.remove("--version")
    sys.argv.append("--deps")
    with pytest.raises(SystemExit):
        before_pipeline("fastqc")


def test_feature_counts():
    p = argparse.ArgumentParser()
    so = FeatureCountsOptions()
    so.add_options(p)


def test_trimming_options():

    p = argparse.ArgumentParser()
    so = TrimmingOptions()
    so.add_options(p)
    p.parse_args(["--trimming-quality", "40"])
    with pytest.raises(SystemExit):
        p.parse_args(["--trimming-quality", "-40"])


def test_snakemake_options():

    p = argparse.ArgumentParser()
    so = SnakemakeOptions()
    so._default_jobs()  # test sheduler
    so.add_options(p)
    p.parse_args([])


def test_krakenl_options():

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


def test_click_general_options():
    from sequana_pipetools.options import (
        ClickGeneralOptions, 
        ClickSlurmOptions, 
        ClickSnakemakeOptions,
        ClickFeatureCountsOptions,
        ClickTrimmingOptions,
        ClickKrakenOptions,
        ClickInputOptions, include_options_from)
    import rich_click as click

    click.rich_click.OPTION_GROUPS = {
        f"sequana_TEST": [],
    }


    @click.command()
    @include_options_from(ClickGeneralOptions)
    @include_options_from(ClickSlurmOptions)
    @include_options_from(ClickInputOptions)
    @include_options_from(ClickSnakemakeOptions)
    @include_options_from(ClickKrakenOptions)
    @include_options_from(ClickFeatureCountsOptions)
    @include_options_from(ClickTrimmingOptions)
    def main(**kwargs):
        pass
    with pytest.raises(SystemExit):
        main(["--help"])

