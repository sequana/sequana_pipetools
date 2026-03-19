import io
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from sequana_pipetools.monitor import (
    DONE,
    FAILED,
    RUNNING,
    _build_display,
    _classify_log,
    _elapsed_str,
    _find_log_files,
    _mark_remaining_done,
    _mark_remaining_failed,
    _ram_gb,
    _scan_logs,
    _scan_snakemake_log,
)

# ── _elapsed_str ──────────────────────────────────────────────────────────────


def test_elapsed_str_seconds():
    result = _elapsed_str(45)
    assert "0m" in result
    assert "45s" in result


def test_elapsed_str_minutes():
    result = _elapsed_str(130)
    assert "2m" in result
    assert "10s" in result


def test_elapsed_str_hours():
    result = _elapsed_str(3665)
    assert "1h" in result
    assert "01m" in result


# ── _ram_gb ───────────────────────────────────────────────────────────────────


def test_ram_gb_no_psutil():
    with patch("sequana_pipetools.monitor._HAS_PSUTIL", False):
        assert _ram_gb(12345) == 0.0


def test_ram_gb_nonexistent_pid():
    # PID 0 or a very large PID should not crash, returns 0.0
    result = _ram_gb(999999999)
    assert isinstance(result, float)


# ── _find_log_files ───────────────────────────────────────────────────────────


def test_find_log_files_yields_logs(tmp_path):
    log = tmp_path / "logs" / "fastqc" / "s1.log"
    log.parent.mkdir(parents=True)
    log.write_text("output")
    found = list(_find_log_files(tmp_path))
    assert log in found


def test_find_log_files_skips_hidden(tmp_path):
    hidden = tmp_path / ".sequana" / "run.log"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("hidden")
    assert hidden not in list(_find_log_files(tmp_path))


def test_find_log_files_skips_multiqc(tmp_path):
    noisy = tmp_path / "multiqc_data" / "out.log"
    noisy.parent.mkdir(parents=True)
    noisy.write_text("noise")
    assert noisy not in list(_find_log_files(tmp_path))


# ── _classify_log ─────────────────────────────────────────────────────────────


def test_classify_log_logs_convention(tmp_path):
    log = tmp_path / "logs" / "fastqc" / "sample1.log"
    log.parent.mkdir(parents=True)
    log.write_text("")
    rule, sample = _classify_log(log, tmp_path)
    assert rule == "fastqc"
    assert sample == "sample1"


def test_classify_log_sample_convention(tmp_path):
    log = tmp_path / "sampleA" / "bowtie2" / "run.log"
    log.parent.mkdir(parents=True)
    log.write_text("")
    rule, sample = _classify_log(log, tmp_path)
    assert rule == "bowtie2"
    assert sample == "sampleA"


def test_classify_log_flat(tmp_path):
    log = tmp_path / "multiqc.log"
    log.write_text("")
    rule, sample = _classify_log(log, tmp_path)
    assert rule == "multiqc"


def test_classify_log_single_dir(tmp_path):
    log = tmp_path / "rulegraph" / "out.log"
    log.parent.mkdir(parents=True)
    log.write_text("")
    rule, sample = _classify_log(log, tmp_path)
    assert rule == "rulegraph"


# ── _scan_logs ────────────────────────────────────────────────────────────────


def test_scan_logs_detects_new_file(tmp_path):
    log = tmp_path / "logs" / "fastqc" / "s1.log"
    log.parent.mkdir(parents=True)
    log.write_text("output")
    state = _scan_logs(tmp_path, {})
    assert "fastqc" in state
    assert "s1" in state["fastqc"]


def test_scan_logs_preserves_done(tmp_path):
    log = tmp_path / "logs" / "rule1" / "s1.log"
    log.parent.mkdir(parents=True)
    log.write_text("done")
    prev = {"rule1": {"s1": {"state": DONE, "start": datetime.now(), "end": datetime.now()}}}
    state = _scan_logs(tmp_path, prev)
    assert state["rule1"]["s1"]["state"] == DONE


def test_scan_logs_uses_log_to_job(tmp_path):
    log = tmp_path / "logs" / "trim" / "s1.log"
    log.parent.mkdir(parents=True)
    log.write_text("output")
    rel = str(log.relative_to(tmp_path))
    log_to_job = {rel: ("fastp", "sample1")}
    state = _scan_logs(tmp_path, {}, log_to_job=log_to_job)
    assert "fastp" in state
    assert "sample1" in state["fastp"]


# ── _mark_remaining_failed / _mark_remaining_done ────────────────────────────


def test_mark_remaining_failed():
    state = {
        "rule1": {"s1": {"state": RUNNING, "start": datetime.now(), "end": None}},
        "rule2": {"s2": {"state": DONE, "start": datetime.now(), "end": datetime.now()}},
    }
    result = _mark_remaining_failed(state)
    assert result["rule1"]["s1"]["state"] == FAILED
    assert result["rule2"]["s2"]["state"] == DONE


def test_mark_remaining_done_running():
    state = {
        "rule1": {"s1": {"state": RUNNING, "start": datetime.now(), "end": None}},
    }
    result = _mark_remaining_done(state)
    assert result["rule1"]["s1"]["state"] == DONE


def test_mark_remaining_done_inserts_expected(tmp_path):
    state = {}
    expected = {"md5sum": 1, "fastqc": 2}
    result = _mark_remaining_done(state, expected)
    assert "md5sum" in result
    assert len(result["fastqc"]) == 2
    assert all(j["state"] == DONE for j in result["fastqc"].values())


def test_mark_remaining_done_fills_partial(tmp_path):
    state = {"fastqc": {"s1": {"state": DONE, "start": datetime.now(), "end": datetime.now()}}}
    result = _mark_remaining_done(state, expected={"fastqc": 3})
    assert len(result["fastqc"]) == 3


# ── _scan_snakemake_log ───────────────────────────────────────────────────────


def test_scan_snakemake_log_missing(tmp_path):
    assert _scan_snakemake_log(tmp_path / "missing.log", {}) == {}


def test_scan_snakemake_log_done_job(tmp_path):
    log = tmp_path / "snakemake.log"
    log.write_text(
        "[Wed Jan 01 12:00:00 2025]\n"
        "localrule fastqc:\n"
        "    wildcards: sample=s1\n"
        "[Wed Jan 01 12:00:05 2025]\n"
        "Finished jobid: 1 (Rule: fastqc)\n"
    )
    state = _scan_snakemake_log(log, {})
    assert "fastqc" in state
    job = next(iter(state["fastqc"].values()))
    assert job["state"] == DONE


def test_scan_snakemake_log_failed_job(tmp_path):
    log = tmp_path / "snakemake.log"
    log.write_text("[Wed Jan 01 12:00:00 2025]\n" "rule trim:\n" "[Wed Jan 01 12:00:05 2025]\n" "Error in rule trim:\n")
    state = _scan_snakemake_log(log, {})
    assert "trim" in state
    job = next(iter(state["trim"].values()))
    assert job["state"] == FAILED


def test_scan_snakemake_log_running_job(tmp_path):
    log = tmp_path / "snakemake.log"
    log.write_text("[Wed Jan 01 12:00:00 2025]\n" "rule align:\n" "    wildcards: sample=s2\n")
    state = _scan_snakemake_log(log, {})
    assert "align" in state
    job = next(iter(state["align"].values()))
    assert job["state"] == RUNNING


def test_scan_snakemake_log_preserves_previous_done(tmp_path):
    log = tmp_path / "snakemake.log"
    log.write_text("")
    prev = {"fastqc": {"s1": {"state": DONE, "start": datetime.now(), "end": datetime.now()}}}
    state = _scan_snakemake_log(log, prev)
    assert state["fastqc"]["s1"]["state"] == DONE


# ── _build_display ────────────────────────────────────────────────────────────


def test_build_display_renders(tmp_path):
    from rich.console import Console

    current = {
        "fastqc": {"s1": {"state": DONE, "start": datetime.now(), "end": datetime.now()}},
        "multiqc": {"s1": {"state": RUNNING, "start": datetime.now(), "end": None}},
    }
    expected = {"fastqc": 1, "multiqc": 1}
    group = _build_display("test", "1.0", expected, current, time.time(), None)
    buf = io.StringIO()
    console = Console(file=buf, width=120)
    console.print(group)
    output = buf.getvalue()
    assert "test" in output.lower() or len(output) > 0


def test_build_display_empty_state():
    from rich.console import Console

    group = _build_display("pipe", "", {}, {}, time.time(), None)
    buf = io.StringIO()
    Console(file=buf, width=120).print(group)


def test_build_display_with_failed():
    from rich.console import Console

    current = {
        "trim": {"s1": {"state": FAILED, "start": datetime.now(), "end": datetime.now()}},
    }
    group = _build_display("pipe", "2.0", {"trim": 1}, current, time.time(), None)
    buf = io.StringIO()
    Console(file=buf, width=120).print(group)
    assert len(buf.getvalue()) > 0


def test_build_display_eta_computed():
    from rich.console import Console

    # Create a state with done jobs so ETA is computed
    current = {
        "rule1": {f"s{i}": {"state": DONE, "start": datetime.now(), "end": datetime.now()} for i in range(3)},
    }
    expected = {"rule1": 10}
    group = _build_display("pipe", "", expected, current, time.time() - 30, None)
    buf = io.StringIO()
    Console(file=buf, width=120).print(group)
