"""CLI entry point: sequana_pipetools_monitor

Called from a pipeline's runme.sh when --monitor was requested at setup time.
"""
import sys

import rich_click as click

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--snakefile", required=True, help="Snakemake rules file (e.g. rnaseq.rules)")
@click.option("--profile", required=True, help="Snakemake profile directory (e.g. .sequana/profile_local)")
@click.option("--name", default="Pipeline", show_default=True, help="Pipeline name for display")
@click.option("--version", default="", show_default=True, help="Pipeline version for display")
@click.option("--workdir", default=".", show_default=True, type=click.Path(), help="Working directory")
def main(snakefile, profile, name, version, workdir):
    """Run a Sequana pipeline with a live rich progress display.

    Watches logs/<rule>/<sample>.log files to track per-step progress.
    Falls back to plain snakemake output when stdout is not a terminal.
    """
    from sequana_pipetools.monitor import run_monitor

    sys.exit(run_monitor(snakefile, profile, name, version, workdir))


if __name__ == "__main__":  # pragma: no cover
    main()
