import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest

from sequana_pipetools.options import (
    ClickGeneralOptions,
    ClickTrimmingOptions,
    OptionEatAll,
)

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


def test_version_callback_with_value():
    ctx = MagicMock()
    ctx.NAME = "test_pipeline"
    with patch("sequana_pipetools.options.print_version") as mock_pv:
        ClickGeneralOptions.version_callback(ctx, None, True)
    mock_pv.assert_called_once_with("test_pipeline")
    ctx.exit.assert_called_once_with(0)


def test_version_callback_no_value():
    result = ClickGeneralOptions.version_callback(MagicMock(), None, False)
    assert result is None


def test_from_project_callback_with_value():
    option = MagicMock()
    option.required = True
    ctx = MagicMock()
    ctx.command.params = [option]
    result = ClickGeneralOptions.from_project_callback(ctx, None, "some/path")
    assert result == "some/path"
    assert option.required is False


def test_from_project_callback_no_value():
    result = ClickGeneralOptions.from_project_callback(MagicMock(), None, None)
    assert result is None


def test_deps_callback_no_value():
    result = ClickGeneralOptions.deps_callback(None, None, False)
    assert result is None


def test_trimming_quality_via_cli():
    import rich_click as click
    from click.testing import CliRunner

    from sequana_pipetools.options import (
        ClickTrimmingOptions,
        include_options_from,
        init_click,
    )

    init_click("TEST2")

    @click.command()
    @include_options_from(ClickTrimmingOptions)
    def cmd(**kwargs):
        click.echo(f"quality={kwargs.get('trimming_quality')}")

    runner = CliRunner()
    # valid positive quality → inner quality() function called
    result = runner.invoke(cmd, ["--trimming-quality", "20"])
    assert result.exit_code == 0
    assert "quality=20" in result.output

    # -1 is the special sentinel value, should also be accepted
    result = runner.invoke(cmd, ["--trimming-quality", "-1"])
    assert result.exit_code == 0
    assert "quality=-1" in result.output
