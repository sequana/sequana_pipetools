from sequana_pipetools.options import *
from easydev import AttrDict
import argparse





def test_cutadapt_options():

    p = argparse.ArgumentParser()
    so = CutadaptOptions()
    so.add_options(p)

    # test the adapter choice
    for this in ["universal", "PCRFree", "none"]:
        options = {
            "cutadapt_adapter_choice": this,
            "cutadapt_design_file": None,
            "cutadapt_fwd": None,
            "cutadapt_rev": None,
            "skip_cutadapt": False,
        }
        #p.parse_args([])
        options = AttrDict(**options)
        so.check_options(options)

    # This one fails because a design and fwd/rev are provided together
    for this in ["universal", "PCRFree", "none"]:
        options = {
            "cutadapt_adapter_choice": this,
            "cutadapt_design_file": "whatever",
            "cutadapt_fwd": "ACGT",
            "cutadapt_rev": "ACGT",
            "skip_cutadapt": False,
        }
        #p.parse_args([])
        options = AttrDict(**options)
        try:
            so.check_options(options)
            assert False
        except: assert True

    # This one fails because a design but not adapter choice
    options = {
        "cutadapt_adapter_choice": None,
        "cutadapt_design_file": "whatever",
        "cutadapt_fwd": None,
        "cutadapt_rev": None,
        "skip_cutadapt": False,
    }
    options = AttrDict(**options)
    try:
        so.check_options(options)
        assert False
    except: assert True

    # This one fails because adapter file is not correct
    options = {
        "cutadapt_adapter_choice": "PCRFree",
        "cutadapt_design_file": "whatever",
        "cutadapt_fwd": None,
        "cutadapt_rev": None,
        "skip_cutadapt": False,
    }
    options = AttrDict(**options)
    try:
        so.check_options(options)
        assert False
    except: assert True


    # wrong combo (missing adapter choice)
    options = {
        "cutadapt_adapter_choice": None,
        "cutadapt_design_file": None,
        "cutadapt_fwd": None,
        "cutadapt_rev": None,
        "skip_cutadapt": False,
    }
    options = AttrDict(**options)
    try:
        so.check_options(options)
        assert False
    except: assert True

    # wrong quality (missing adapter choice)
    try:
        p.parse_args(["--cutadapt-quality", "-1"])
        assert False
    except: assert True
    p.parse_args(["--cutadapt-quality", "10"])

    # test for a valid design and adapter choice but also fwd/rev provided
    # whereas, we cannot do anything with this combo
    options = {
        "cutadapt_adapter_choice": "TruSeq",
        "cutadapt_design_file": None,
        "cutadapt_fwd": "ACGT",  # dummy values
        "cutadapt_rev": "CGTA",  # dummy values
        "skip_cutadapt": False,
    }
    options = AttrDict(**options)
    try:
        so.check_options(options)
        assert False
    except: assert True


def test_snakemake_options():
    from sequana_pipetools.options import SnakemakeOptions
    p = argparse.ArgumentParser()
    so = SnakemakeOptions()
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
