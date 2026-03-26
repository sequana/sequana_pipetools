import os
import sys
from unittest.mock import patch

from click.testing import CliRunner

from sequana_pipetools.scripts.main import ClickComplete, _print_diagnosis, main
from sequana_pipetools.scripts.monitor import main as monitor_main

from . import test_dir


def test_main():
    runner = CliRunner()
    results = runner.invoke(main, ["--help"])
    assert results.exit_code == 0


def test_version():
    runner = CliRunner()
    results = runner.invoke(main, ["--version"])
    assert results.exit_code == 0


def test_completion(monkeypatch):

    # FIXME
    # monkeypatch.setattr("builtins.input", lambda x: "y")
    # runner = CliRunner()
    # results = runner.invoke(main, ["--completion", "rnaseq"])
    # assert results.exit_code == 0

    runner = CliRunner()
    results = runner.invoke(main, ["--completion", "fastqc", "--overwrite"])
    assert results.exit_code == 0


def test_url2hash():
    runner = CliRunner()
    results = runner.invoke(main, ["--url2hash", "test"])
    assert results.exit_code == 0
    assert results.output == "098f6bcd4621d373cade4e832627b4f6\n"


def test_stats():
    runner = CliRunner()
    results = runner.invoke(main, ["--stats"])
    assert results.exit_code == 0


def test_config_to_schema():
    runner = CliRunner()
    results = runner.invoke(main, ["--config-to-schema", f"{test_dir}/data/config.yaml"])
    assert results.exit_code == 0


def test_slurm_diag():
    runner = CliRunner()
    results = runner.invoke(main, ["--slurm-diag"])
    assert results.exit_code == 0


def test_dot2png(tmpdir):
    runner = CliRunner()
    dotfile = os.path.join(test_dir, "..", "data", "test_dag.dot")
    results = runner.invoke(main, ["--dot2png", dotfile])
    assert results.exit_code == 0


def test_diagnose(tmp_path):
    runner = CliRunner()
    with patch("sequana_pipetools.diagnose.diagnose", return_value="All good.") as mock_diag:
        results = runner.invoke(main, ["--diagnose", "--workdir", str(tmp_path)])
    assert results.exit_code == 0
    assert "All good." in results.output
    mock_diag.assert_called_once_with(workdir=str(tmp_path), provider="mistral", model=None)


def test_diagnose_error(tmp_path):
    runner = CliRunner()
    with patch("sequana_pipetools.diagnose.diagnose", side_effect=EnvironmentError("no key")):
        results = runner.invoke(main, ["--diagnose", "--workdir", str(tmp_path)])
    assert results.exit_code == 1
    assert "no key" in results.output


def test_monitor_help():
    runner = CliRunner()
    results = runner.invoke(monitor_main, ["--help"])
    assert results.exit_code == 0
    assert "--snakefile" in results.output


def test_monitor_runs(tmp_path):
    runner = CliRunner()
    with patch("sequana_pipetools.monitor.run_monitor", return_value=0) as mock_run:
        results = runner.invoke(
            monitor_main,
            [
                "--snakefile",
                "pipeline.rules",
                "--profile",
                ".sequana/profile_local",
                "--name",
                "test",
                "--workdir",
                str(tmp_path),
            ],
        )
    assert results.exit_code == 0
    mock_run.assert_called_once_with("pipeline.rules", ".sequana/profile_local", "test", "", str(tmp_path))


# ── _print_diagnosis ──────────────────────────────────────────────────────────


def test_print_diagnosis_with_tips():
    """Result containing the tips separator renders without error."""
    _print_diagnosis("Some LLM analysis output.\n---\nSequana tip: check your slurm logs.")


def test_print_diagnosis_with_plain_explanation():
    """Plain Explanation section is extracted into a Rich panel."""
    result = (
        "## Analysis\n"
        "Some context.\n\n"
        "## Plain Explanation\n"
        "The error is caused by a missing tool.\n\n"
        "## Technical Details\n"
        "Traceback shown here.\n"
    )
    _print_diagnosis(result)


def test_print_diagnosis_plain_explanation_and_tips():
    """Both Plain Explanation regex and tips separator are exercised."""
    result = "## Plain Explanation\n" "Install the missing dependency.\n" "\n---\n" "Sequana tip: use --diagnose."
    _print_diagnosis(result)


def test_print_diagnosis_no_match():
    """Result with no special sections renders the raw text."""
    _print_diagnosis("Simple error message without any structured sections.")


# ── ClickComplete.set_option_file ─────────────────────────────────────────────


def test_set_option_file():
    """set_option_file generates valid bash completion snippet."""
    cc = ClickComplete.__new__(ClickComplete)
    result = cc.set_option_file("--my-file")
    assert "--my-file" in result
    assert "compgen" in result


# ── dot2png bad extension ─────────────────────────────────────────────────────


def test_dot2png_bad_extension():
    """--dot2png with a non-.dot file raises ValueError (caught by Click)."""
    runner = CliRunner()
    results = runner.invoke(main, ["--dot2png", "notadotfile.txt"])
    assert results.exit_code != 0
