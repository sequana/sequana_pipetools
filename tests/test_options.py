import argparse
import sys

import pytest

from sequana_pipetools.options import ClickGeneralOptions, OptionEatAll

# for test_click_general_options() to work we need to define a global variable
NAME = "TEST"


def test_click_general_options():
    import rich_click as click

    from sequana_pipetools.options import (
        ClickFeatureCountsOptions,
        ClickGeneralOptions,
        ClickInputOptions,
        ClickKrakenOptions,
        ClickSlurmOptions,
        ClickSnakemakeOptions,
        ClickTrimmingOptions,
        include_options_from,
        init_click,
    )

    init_click("TEST", groups={"test": 1})

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

    with pytest.raises(SystemExit):
        main(["--version"])

    # with pytest.raises(ValueError, SystemExit):
    #    main(["--from-project"])

    with pytest.raises(ValueError):
        main(["--deps"])


def test_click_option_eat_all():
    import ast

    import click
    from click.testing import CliRunner

    def check_databases(ctx, param, value):
        if value:
            # click transform the input databases  (tuple) into a string
            # we need to convert it back to a tuple before checking the databases
            values = ast.literal_eval(value)
            for db in values:
                click.echo(f"{db} used")
        return ast.literal_eval(value)

    @click.option("--databases", "databases", type=click.STRING, cls=OptionEatAll, callback=check_databases)
    def main(**options):
        pass

    main.name = "root"

    runner = CliRunner()
    runner.invoke(main, ["--databases", "1", "2"])
