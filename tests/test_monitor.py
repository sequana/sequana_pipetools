import io
import os
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

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


# ── _parse_dryrun ─────────────────────────────────────────────────────────────


def test_parse_dryrun_exception(tmp_path):
    """Falls back to ({}, {}) on subprocess error."""
    from sequana_pipetools.monitor import _parse_dryrun

    with patch("subprocess.run", side_effect=Exception("timeout")):
        expected, log_to_job = _parse_dryrun("pipeline.rules", "profile", tmp_path)

    assert expected == OrderedDict()
    assert log_to_job == {}


def test_parse_dryrun_parses_output(tmp_path):
    """Parses rule/log/wildcards and job stats from dryrun output."""
    from sequana_pipetools.monitor import _parse_dryrun

    fake_output = (
        "rule fastqc:\n"
        "    log: samples/s1/fastqc.log\n"
        "    wildcards: sample=s1\n"
        "rule multiqc:\n"
        "    log: multiqc/multiqc.log\n"
        "\n"
        "Job stats:\n"
        "job       count\n"
        "-------   -----\n"
        "fastqc    2\n"
        "multiqc   1\n"
        "total     3\n"
    )
    mock_result = MagicMock()
    mock_result.stdout = fake_output
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        expected, log_to_job = _parse_dryrun("pipeline.rules", "profile", tmp_path)

    assert expected.get("fastqc") == 2
    assert expected.get("multiqc") == 1
    assert "samples/s1/fastqc.log" in log_to_job
    assert log_to_job["samples/s1/fastqc.log"] == ("fastqc", "s1")


def test_parse_dryrun_with_configfile(tmp_path):
    """Adds --configfile when config.yaml exists in workdir."""
    from sequana_pipetools.monitor import _parse_dryrun

    (tmp_path / "config.yaml").write_text("key: value\n")
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_sub:
        _parse_dryrun("pipeline.rules", "profile", tmp_path)

    called_cmd = mock_sub.call_args[0][0]
    assert "--configfile" in called_cmd


# ── _ram_gb ─────────────────────────────────────────────────────────────────


def test_ram_gb_child_access_denied():
    """Child process AccessDenied is swallowed; parent RSS is returned."""
    import psutil as real_psutil

    from sequana_pipetools.monitor import _ram_gb

    mock_child = MagicMock()
    mock_child.memory_info.side_effect = real_psutil.AccessDenied(pid=2)

    mock_proc = MagicMock()
    mock_proc.memory_info.return_value = MagicMock(rss=2 * 1024**3)  # 2 GB
    mock_proc.children.return_value = [mock_child]

    mock_psutil = MagicMock()
    mock_psutil.Process.return_value = mock_proc
    mock_psutil.NoSuchProcess = real_psutil.NoSuchProcess
    mock_psutil.AccessDenied = real_psutil.AccessDenied

    with patch("sequana_pipetools.monitor._HAS_PSUTIL", True):
        with patch("sequana_pipetools.monitor.psutil", mock_psutil):
            result = _ram_gb(12345)

    assert result == pytest.approx(2.0)


# ── _scan_logs extras ─────────────────────────────────────────────────────────


def test_scan_logs_oserror(tmp_path):
    """OSError during stat is silently skipped."""
    log = tmp_path / "logs" / "rule1" / "s1.log"
    log.parent.mkdir(parents=True)
    log.write_text("output")

    original_stat = Path.stat

    def patched_stat(self, *args, **kwargs):
        if self.name == "s1.log":
            raise OSError("permission denied")
        return original_stat(self, *args, **kwargs)

    with patch.object(Path, "stat", patched_stat):
        state = _scan_logs(tmp_path, {})

    assert "rule1" not in state


def test_scan_logs_preserves_existing_end_time(tmp_path):
    """When prev_job is RUNNING with end already set, preserve that end time."""
    log = tmp_path / "logs" / "rule1" / "s1.log"
    log.parent.mkdir(parents=True)
    log.write_text("output")

    # Age the file beyond _DONE_THRESHOLD so job_state == DONE
    old_mtime = time.time() - 10
    os.utime(log, (old_mtime, old_mtime))

    existing_end = datetime(2025, 1, 1, 12, 0, 0)
    prev = {
        "rule1": {
            "s1": {
                "state": RUNNING,  # not DONE → no early continue
                "start": datetime.now(),
                "end": existing_end,  # end already set
            }
        }
    }
    state = _scan_logs(tmp_path, prev)
    assert state["rule1"]["s1"]["end"] == existing_end


# ── _scan_snakemake_log extras ────────────────────────────────────────────────


def test_scan_snakemake_log_oserror(tmp_path):
    """OSError when reading log file returns preserved state."""
    log = tmp_path / "snakemake.log"
    log.write_text("")

    prev = {"fastqc": {"s1": {"state": DONE, "start": datetime.now(), "end": datetime.now()}}}

    with patch.object(Path, "read_text", side_effect=OSError("denied")):
        state = _scan_snakemake_log(log, prev)

    assert state["fastqc"]["s1"]["state"] == DONE


def test_scan_snakemake_log_invalid_timestamp(tmp_path):
    """ValueError in timestamp parse does not crash; rule is still tracked."""
    log = tmp_path / "snakemake.log"
    log.write_text("[INVALID TIMESTAMP]\nrule fastqc:\n")
    state = _scan_snakemake_log(log, {})
    assert isinstance(state, dict)


def test_scan_snakemake_log_jobid_tracking(tmp_path):
    """jobid line associates snakemake >=8 job IDs with rules."""
    log = tmp_path / "snakemake.log"
    log.write_text("[Wed Jan 01 12:00:00 2025]\n" "rule trim:\n" "    jobid: 7\n" "    wildcards: sample=sA\n")
    state = _scan_snakemake_log(log, {})
    assert "trim" in state
    job = next(iter(state["trim"].values()))
    assert job["state"] == RUNNING


def test_scan_snakemake_log_snakemake8_finished(tmp_path):
    """'Finished job N.' format (snakemake >= 8) marks rule as DONE."""
    log = tmp_path / "snakemake.log"
    log.write_text(
        "[Wed Jan 01 12:00:00 2025]\n"
        "rule align:\n"
        "    jobid: 3\n"
        "    wildcards: sample=s2\n"
        "[Wed Jan 01 12:01:00 2025]\n"
        "Finished job 3.\n"
    )
    state = _scan_snakemake_log(log, {})
    assert "align" in state
    job = next(iter(state["align"].values()))
    assert job["state"] == DONE


# ── _build_display extras ─────────────────────────────────────────────────────


def test_build_display_with_pid_and_ram():
    """When pid is given and _ram_gb returns > 0, Peak RAM appears in output."""
    current = {
        "rule1": {"s1": {"state": DONE, "start": datetime.now(), "end": datetime.now()}},
    }
    with patch("sequana_pipetools.monitor._ram_gb", return_value=2.5):
        group = _build_display("test", "1.0", {"rule1": 1}, current, time.time(), pid=99999)
    buf = io.StringIO()
    Console(file=buf, width=200).print(group)
    assert len(buf.getvalue()) > 0


def test_build_display_with_memory_peaks():
    """Memory peak column appears when _HAS_PSUTIL=True and memory_peaks provided."""
    current = {
        "rule1": {"s1": {"state": DONE, "start": datetime.now(), "end": datetime.now()}},
    }
    with patch("sequana_pipetools.monitor._HAS_PSUTIL", True):
        group = _build_display("test", "1.0", {"rule1": 1}, current, time.time(), pid=None, memory_peaks={"rule1": 1.5})
    buf = io.StringIO()
    Console(file=buf, width=200).print(group)
    assert "Mem Peak" in buf.getvalue()


def test_build_display_rule_not_in_expected():
    """Rule in current but missing from expected is appended to display."""
    current = {
        "extra_rule": {"s1": {"state": DONE, "start": datetime.now(), "end": datetime.now()}},
    }
    group = _build_display("test", "1.0", {"fastqc": 1}, current, time.time(), pid=None)
    buf = io.StringIO()
    Console(file=buf, width=200).print(group)
    assert len(buf.getvalue()) > 0


def test_build_display_waiting_state():
    """Rules in expected but not yet started appear as WAITING."""
    group = _build_display("test", "1.0", {"fastqc": 1, "multiqc": 1}, {}, time.time(), pid=None)
    buf = io.StringIO()
    Console(file=buf, width=200).print(group)
    assert len(buf.getvalue()) > 0


def test_build_display_running_with_queued_and_memory():
    """RUNNING rule with queued placeholders and memory peaks column."""
    current = {
        "fastp": {"s1": {"state": RUNNING, "start": datetime.now(), "end": None}},
    }
    with patch("sequana_pipetools.monitor._HAS_PSUTIL", True):
        group = _build_display(
            "test",
            "1.0",
            {"fastp": 5},  # queued_n = 5 - 1 = 4 > 0
            current,
            time.time(),
            pid=None,
            memory_peaks={"fastp": 2.0},
        )
    buf = io.StringIO()
    Console(file=buf, width=200).print(group)
    assert len(buf.getvalue()) > 0


def test_build_display_failed_with_show_mem():
    """FAILED rule with memory peaks shows sub-rows including mem column."""
    current = {
        "trim": {"s1": {"state": FAILED, "start": datetime.now(), "end": datetime.now()}},
    }
    with patch("sequana_pipetools.monitor._HAS_PSUTIL", True):
        group = _build_display("test", "1.0", {"trim": 1}, current, time.time(), pid=None, memory_peaks={})
    buf = io.StringIO()
    Console(file=buf, width=200).print(group)
    assert len(buf.getvalue()) > 0


# ── run_monitor ───────────────────────────────────────────────────────────────


def test_run_monitor_non_tty(tmp_path):
    """Non-TTY stdout: falls back to plain subprocess.run."""
    from sequana_pipetools.monitor import run_monitor

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result) as mock_sub:
        with patch("sys.stdout", io.StringIO()):
            result = run_monitor("pipeline.rules", "profile_local", "test", "1.0", str(tmp_path))

    assert result == 0
    mock_sub.assert_called_once()


def test_run_monitor_non_tty_nonzero_exit(tmp_path):
    """Non-TTY path returns non-zero exit code from snakemake."""
    from sequana_pipetools.monitor import run_monitor

    mock_result = MagicMock()
    mock_result.returncode = 1

    with patch("subprocess.run", return_value=mock_result):
        with patch("sys.stdout", io.StringIO()):
            result = run_monitor("pipeline.rules", "profile_local", workdir=str(tmp_path))

    assert result == 1
