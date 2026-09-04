import os
import sys
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from sequana_pipetools.external_runner import create_wrapper_rulegraph
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


# ── dot2png from stdin ────────────────────────────────────────────────────────


def test_dot2png_stdin(tmp_path, monkeypatch):
    """--dot2png - reads the dot file (e.g. snakemake --rulegraph) from stdin."""
    monkeypatch.chdir(tmp_path)
    dotfile = os.path.join(test_dir, "..", "data", "test_dag.dot")
    with open(dotfile, "r") as fin:
        content = fin.read()

    runner = CliRunner()
    results = runner.invoke(main, ["--dot2png", "-"], input=content)
    assert results.exit_code == 0
    assert (tmp_path / "rulegraph.sequana.png").exists()


def test_dot2png_stdin_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dotfile = os.path.join(test_dir, "..", "data", "test_dag.dot")
    with open(dotfile, "r") as fin:
        content = fin.read()

    runner = CliRunner()
    results = runner.invoke(main, ["--dot2png", "-", "-o", "test.png"], input=content)
    assert results.exit_code == 0
    assert (tmp_path / "test.png").exists()


def test_dot2png_stdin_empty():
    runner = CliRunner()
    results = runner.invoke(main, ["--dot2png", "-"], input="")
    assert results.exit_code != 0


def test_dotparser_no_input():
    from sequana_pipetools.snaketools import DOTParser

    with pytest.raises(ValueError):
        DOTParser()


def test_dot2png_bad_content(tmp_path, monkeypatch):
    """A non-dot input makes graphviz fail: no success message, non-zero exit."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    results = runner.invoke(main, ["--dot2png", "-"], input="this is not dot\n")
    assert results.exit_code != 0
    assert "Created" not in results.output


def test_dot2png_output_with_spaces(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dotfile = os.path.join(test_dir, "..", "data", "test_dag.dot")
    with open(dotfile, "r") as fin:
        content = fin.read()

    runner = CliRunner()
    results = runner.invoke(main, ["--dot2png", "-", "-o", "my file.png"], input=content)
    assert results.exit_code == 0
    assert (tmp_path / "my file.png").exists()


def test_output_without_dot2png():
    runner = CliRunner()
    results = runner.invoke(main, ["--output", "test.png"])
    assert results.exit_code != 0
    assert "--dot2png" in results.output


def test_create_wrapper_rulegraph(tmp_path):
    snakefile = tmp_path / "Snakefile"
    snakefile.write_text("rule all:\n    input: []\n")
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / ".sequana").mkdir()

    dot_content = "digraph snakemake_dag { all[label = \"all\"]; }\n"

    with patch("sequana_pipetools.external_runner.subprocess.run") as mock_run:
        with patch("sequana_pipetools.external_runner.convert_dot_to_png") as mock_convert:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = dot_content
            result = create_wrapper_rulegraph(str(snakefile), ".sequana/profile_local", workdir)

    assert result == workdir / ".sequana" / "rulegraph.sequana.png"
    assert (workdir / ".sequana" / "rulegraph.dot").read_text() == dot_content
    mock_convert.assert_called_once_with(
        str(workdir / ".sequana" / "rulegraph.dot"), output=str(workdir / ".sequana" / "rulegraph.sequana.png")
    )


def test_wrapper_runs_and_writes_summary(tmp_path):
    runner = CliRunner()
    snakefile = tmp_path / "Snakefile"
    snakefile.write_text("rule all:\n    input: []\n")
    workdir = tmp_path / "analysis"
    (workdir / ".sequana" / "profile_local").mkdir(parents=True)
    (workdir / ".sequana" / "profile_local" / "config.yaml").write_text("cores: 2\n")
    (workdir / ".sequana" / "rulegraph.sequana.png").write_text("png")

    with patch("sequana_pipetools.external_runner.create_profile", return_value=".sequana/profile_local") as mock_profile:
        with patch(
            "sequana_pipetools.external_runner.create_wrapper_rulegraph",
            return_value=workdir / ".sequana" / "rulegraph.sequana.png",
        ) as mock_graph:
            with patch("sequana_pipetools.external_runner.run_monitor", return_value=0) as mock_run:
                results = runner.invoke(
                    main,
                    [
                        "--wrapper",
                        str(snakefile),
                        "--workdir",
                        str(workdir),
                        "--wrapper-name",
                        "My wrapper",
                        "--wrapper-profile",
                        "local",
                        "--wrapper-jobs",
                        "2",
                    ],
                )

    assert results.exit_code == 0
    mock_profile.assert_called_once()
    assert mock_profile.call_args.args[0] == workdir.resolve()
    assert mock_profile.call_args.args[1] == "local"
    assert mock_profile.call_args.kwargs["jobs"] == 2
    mock_graph.assert_called_once_with(str(snakefile.resolve()), ".sequana/profile_local", workdir.resolve())
    mock_run.assert_called_once_with(str(snakefile.resolve()), ".sequana/profile_local", "My wrapper", "", str(workdir))

    summary = workdir / "summary.html"
    assert summary.exists()
    content = summary.read_text()
    assert "My wrapper summary" in content
    assert str(snakefile.resolve()) in content
    assert ".sequana/profile_local/config.yaml" in content
    assert "Rulegraph PNG" in content
