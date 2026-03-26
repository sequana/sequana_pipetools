from __future__ import annotations

"""Rich terminal monitor for Sequana pipelines.

Drives a live display by watching ``logs/<rule>/<sample>.log`` files:
- file appears with fresh mtime  → RUNNING
- file mtime stable for >3 s    → DONE
- subprocess exits non-zero      → remaining RUNNING jobs → FAILED

The monitor runs snakemake as a child process so the user only needs to call
``sh runme.sh`` (or the generated ``sequana_pipetools_monitor`` command).
"""

import os
import re
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import colorlog
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text

from sequana_pipetools.snaketools.pipeline_manager import CITATION_MESSAGE

logger = colorlog.getLogger(__name__)

try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

# ── job states ───────────────────────────────────────────────────────────────

WAITING = "waiting"
RUNNING = "running"
DONE = "done"
FAILED = "failed"

# seconds without mtime change before a log file is considered done
_DONE_THRESHOLD = 3.0


# ── helpers ──────────────────────────────────────────────────────────────────


def _elapsed_str(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def _ram_gb(pid: int) -> float:
    if not _HAS_PSUTIL:
        return 0.0
    try:
        proc = psutil.Process(pid)
        mem = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                mem += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return mem / 1024**3
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0


def _parse_dryrun(snakefile: str, profile: str, workdir: Path):
    """Run snakemake --dryrun and return ``(expected, log_to_job)``.

    ``expected``  – OrderedDict[rule_name, int]: job counts per rule (all rules,
                    including those without log files).
    ``log_to_job`` – dict[str, (rule_name, sample)]: maps a log file's path
                    relative to workdir (as a string) to the snakemake rule name
                    and sample wildcard value.  Built from the dryrun's verbose
                    ``log:`` / ``wildcards:`` output so classification is exact
                    rather than heuristic.

    Falls back to ``({}, {})`` on any error so the monitor still works.
    """
    # Run dryrun without the profile to avoid version-incompatible profile keys
    # (e.g. apptainer-* flags in a v8-style profile on a v7 installation).
    # Pass --configfile if a config.yaml exists in the workdir.
    cmd = ["snakemake", "-s", snakefile, "--dryrun", "--forceall", "--nocolor"]
    configfile = workdir / "config.yaml"
    if configfile.exists():
        cmd += ["--configfile", str(configfile)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=workdir, timeout=120)
        output = result.stdout + result.stderr
    except Exception:
        return OrderedDict(), {}

    log_to_job: dict = {}

    # ── pass 1: parse verbose job blocks to build log_path → (rule, sample) ──
    # Each block looks like:
    #   rule fastqc:
    #       log: samples/Hm2_GTGAAA_L005_R1_001/fastqc.log
    #       wildcards: sample=Hm2_GTGAAA_L005_R1_001
    current_rule: str | None = None
    current_logs: list = []
    current_sample: str | None = None

    def _flush():
        nonlocal current_rule, current_logs, current_sample
        if current_rule and current_logs:
            for lp in current_logs:
                sample = current_sample or Path(lp).stem
                log_to_job[lp] = (current_rule, sample)
        current_rule = None
        current_logs = []
        current_sample = None

    for line in output.splitlines():
        s = line.strip()
        if (s.startswith("rule ") or s.startswith("checkpoint ")) and s.endswith(":"):
            _flush()
            current_rule = s.split()[1].rstrip(":")
        elif current_rule:
            if s.startswith("log:"):
                for lf in s[4:].split(","):
                    lf = lf.strip()
                    if lf:
                        current_logs.append(lf)
            elif s.startswith("wildcards:"):
                for part in s[10:].split(","):
                    part = part.strip()
                    if part.startswith("sample="):
                        current_sample = part[7:].strip()
                        break
    _flush()

    # ── pass 2: job stats section for per-rule counts ─────────────────────────
    expected: OrderedDict = OrderedDict()
    in_stats = False
    for line in output.splitlines():
        low = line.lower()
        if "job stats" in low or "job counts" in low:
            in_stats = True
            continue
        if in_stats:
            parts = line.split()
            if parts and parts[-1].isdigit() and parts[0] not in ("job", "total") and not parts[0].startswith("-"):
                expected[parts[0]] = int(parts[-1])
            elif not line.strip():
                in_stats = False

    return expected, log_to_job


# ── log-file scanner ─────────────────────────────────────────────────────────

# directories to skip while scanning for log files
_SKIP_DIRS = frozenset({"multiqc_data", "multiqc_report_data"})


def _find_log_files(workdir: Path):
    """Recursively yield .log files under workdir, skipping hidden dirs and noise."""
    for path in workdir.rglob("*.log"):
        rel = path.relative_to(workdir)
        parts = rel.parts[:-1]  # directory parts only
        if any(p.startswith(".") or p in _SKIP_DIRS for p in parts):
            continue
        yield path


def _classify_log(path: Path, workdir: Path):
    """Return (rule_name, sample_name) from a log file path.

    Handles the two conventions used by sequana pipelines:
      - ``logs/<rule>/<stem>.log``           (fastp, fix_bowtie1, …)
      - ``<sample>/<rule>/…/<stem>.log``     (bowtie2, fastqc_clean, …)
      - ``<rule>/<stem>.log``                (multiqc, rulegraph, …)
    Numeric-only path components (e.g. feature_counts/0/) are ignored.
    """
    rel = path.relative_to(workdir)
    dirs = [p for p in rel.parts[:-1] if not p.isdigit()]

    if not dirs:
        return path.stem, path.stem

    if dirs[0] == "logs" and len(dirs) >= 2:
        # logs/<rule>/.../<stem>.log
        return dirs[1], path.stem

    # <sample>/<rule>/.../<stem>.log  or  <rule>/<stem>.log
    rule = dirs[-1]
    sample = dirs[0] if len(dirs) >= 2 else path.stem
    return rule, sample


def _scan_logs(workdir: Path, prev: dict, log_to_job: dict | None = None) -> "OrderedDict[str, OrderedDict]":
    """Recursively scan workdir for .log files and return per-rule per-sample state.

    ``log_to_job`` maps relative log path strings to ``(rule, sample)`` tuples
    as returned by ``_parse_dryrun``.  When provided, classification is exact;
    otherwise ``_classify_log`` is used as a fallback.

    ``prev`` is the state from the previous scan; preserves start times and
    avoids resetting a DONE job back to RUNNING.
    """
    state: OrderedDict = OrderedDict()
    now = time.time()

    for log_file in sorted(_find_log_files(workdir)):
        try:
            stat = log_file.stat()
        except OSError:
            continue

        rel_str = str(log_file.relative_to(workdir))
        if log_to_job and rel_str in log_to_job:
            rule, sample = log_to_job[rel_str]
        else:
            rule, sample = _classify_log(log_file, workdir)

        if rule not in state:
            state[rule] = OrderedDict()

        prev_job = prev.get(rule, {}).get(sample)

        if prev_job and prev_job["state"] == DONE:
            state[rule][sample] = prev_job
            continue

        age = now - stat.st_mtime
        job_state = DONE if age > _DONE_THRESHOLD else RUNNING
        start = prev_job["start"] if prev_job else datetime.now()
        # Use datetime.now() when first transitioning to DONE rather than
        # stat.st_mtime: on Linux ctime and mtime update together, so
        # mtime - ctime ≈ 0, giving a near-zero elapsed duration.
        if job_state == DONE:
            if prev_job and prev_job.get("end"):
                end = prev_job["end"]  # preserve existing end time
            else:
                end = datetime.now()  # first DONE detection ≈ real end
        else:
            end = None

        state[rule][sample] = {
            "state": job_state,
            "start": start,
            "end": end,
        }
    return state


_TS_RE = re.compile(r"^\[(\w+ \w+ +\d+ \d+:\d+:\d+ \d+)\]")
_FINISHED_RE = re.compile(r"Finished jobid: \d+ \(Rule: (\w+)\)")  # snakemake <8
_FINISHED_JOB_RE = re.compile(r"^Finished job (\d+)\.")  # snakemake >=8
_JOBID_RE = re.compile(r"^\s+jobid:\s*(\d+)")
_RULE_START_RE = re.compile(r"^(?:local)?rule (\w+):")
_WILDCARDS_RE = re.compile(r"wildcards:\s*sample=(\S+)")
_ERROR_RULE_RE = re.compile(r"Error in (?:rule|checkpoint) (\w+):")


def _scan_snakemake_log(snakelog: Path, prev: dict) -> dict:
    """Parse snakemake's own log to track per-rule job progress.

    This is the primary tracker for pipelines whose rules have no ``log:``
    directive (e.g. slicer).  For rules that *do* produce log files,
    ``_scan_logs`` provides richer sample-name information and takes
    precedence.

    Returns the same ``{rule: {job_key: {state, start, end}}}`` structure
    as ``_scan_logs``.  Job keys are ``sample=<value>`` when a wildcard
    sample can be inferred, otherwise ``job_<n>``.
    """
    if not snakelog.exists():
        return {}

    # Preserve already-DONE entries from previous call
    state: dict = {}
    for rule, jobs in prev.items():
        for key, job in jobs.items():
            if job["state"] in (DONE, FAILED):
                state.setdefault(rule, OrderedDict())[key] = job

    try:
        text = snakelog.read_text(errors="replace")
    except OSError:
        return state

    current_ts: datetime | None = None
    # pending starts per rule: list of (start_ts, sample_name|None, jobid|None)
    pending: dict = {}
    done_count: dict = {}  # rule → int
    jobid_to_rule: dict = {}  # jobid str → rule name  (snakemake >=8)
    last_rule: str | None = None  # rule seen most recently (for jobid association)

    for line in text.splitlines():
        ts_m = _TS_RE.match(line)
        if ts_m:
            try:
                current_ts = datetime.strptime(ts_m.group(1), "%a %b %d %H:%M:%S %Y")
            except ValueError:
                pass
            continue

        # job starting: "localrule X:" or "rule X:"
        rs_m = _RULE_START_RE.match(line.strip())
        if rs_m:
            last_rule = rs_m.group(1)
            pending.setdefault(last_rule, []).append([current_ts or datetime.now(), None, None])
            continue

        # jobid line immediately following rule start (snakemake >=8: "    jobid: 5")
        jid_m = _JOBID_RE.match(line)
        if jid_m and last_rule:
            jid = jid_m.group(1)
            jobid_to_rule[jid] = last_rule
            # attach jobid to the last pending entry for this rule
            starts = pending.get(last_rule, [])
            if starts and starts[-1][2] is None:
                starts[-1][2] = jid
            last_rule = None  # consumed
            continue

        # wildcard on the next line after rule start: grab sample name
        wc_m = _WILDCARDS_RE.search(line)
        if wc_m:
            sample_val = wc_m.group(1).rstrip(",")
            for starts in reversed(list(pending.values())):
                if starts and starts[-1][1] is None:
                    starts[-1][1] = sample_val
                    break
            continue

        # job finished — snakemake >=8: "Finished job 5."
        fin8_m = _FINISHED_JOB_RE.match(line.strip())
        if fin8_m:
            jid = fin8_m.group(1)
            rule = jobid_to_rule.get(jid)
            if rule:
                n = done_count.get(rule, 0)
                starts = pending.get(rule, [])
                # find the pending entry with this jobid
                entry = next((e for e in starts if e[2] == jid), starts[0] if starts else None)
                if entry and entry in starts:
                    starts.remove(entry)
                start_ts, sample_val = (entry[0], entry[1]) if entry else (current_ts, None)
                end_ts = current_ts or datetime.now()
                job_key = f"sample={sample_val}" if sample_val else f"job_{n + 1}"
                state.setdefault(rule, OrderedDict())[job_key] = {
                    "state": DONE,
                    "start": start_ts or end_ts,
                    "end": end_ts,
                }
                done_count[rule] = n + 1
            continue

        # job finished — snakemake <8: "Finished jobid: 5 (Rule: flye)"
        fin_m = _FINISHED_RE.search(line)
        if fin_m:
            rule = fin_m.group(1)
            n = done_count.get(rule, 0)
            starts = pending.get(rule, [])
            start_ts, sample_val, _ = starts.pop(0) if starts else (current_ts, None, None)
            end_ts = current_ts or datetime.now()
            job_key = f"sample={sample_val}" if sample_val else f"job_{n + 1}"
            state.setdefault(rule, OrderedDict())[job_key] = {
                "state": DONE,
                "start": start_ts or end_ts,
                "end": end_ts,
            }
            done_count[rule] = n + 1
            continue

        # job failed
        err_m = _ERROR_RULE_RE.search(line)
        if err_m:
            rule = err_m.group(1)
            n = done_count.get(rule, 0)
            starts = pending.get(rule, [])
            start_ts, sample_val, _ = starts.pop(0) if starts else (current_ts, None, None)
            end_ts = current_ts or datetime.now()
            job_key = f"sample={sample_val}" if sample_val else f"job_{n + 1}"
            state.setdefault(rule, OrderedDict())[job_key] = {
                "state": FAILED,
                "start": start_ts or end_ts,
                "end": end_ts,
            }
            done_count[rule] = n + 1

    # anything still pending → RUNNING
    for rule, starts in pending.items():
        already = len(state.get(rule, {}))
        for i, (start_ts, sample_val, _jid) in enumerate(starts):
            job_key = f"sample={sample_val}" if sample_val else f"job_{already + i + 1}"
            if job_key not in state.get(rule, {}):
                state.setdefault(rule, OrderedDict())[job_key] = {
                    "state": RUNNING,
                    "start": start_ts or datetime.now(),
                    "end": None,
                }

    return state


def _mark_remaining_failed(current: dict) -> dict:
    """Mark any still-RUNNING job as FAILED (called when snakemake exits non-zero)."""
    for rule_jobs in current.values():
        for job in rule_jobs.values():
            if job["state"] == RUNNING:
                job["state"] = FAILED
                job["end"] = datetime.now()
    return current


def _mark_remaining_done(current: dict, expected: dict | None = None) -> dict:
    """Mark any still-RUNNING job as DONE (called when snakemake exits zero).

    Also inserts synthetic DONE entries for rules that appear in ``expected``
    but produced no tracked log files (e.g. ``md5sum``, ``rulegraph``).
    This ensures the final table shows them as Done rather than Waiting.
    """
    now = datetime.now()
    for rule_jobs in current.values():
        for job in rule_jobs.values():
            if job["state"] == RUNNING:
                job["state"] = DONE
                job["end"] = now
    if expected:
        for rule, count in expected.items():
            if rule not in current:
                # Rule produced no tracked log files at all
                current[rule] = {f"_job_{i + 1}": {"state": DONE, "start": now, "end": now} for i in range(count)}
            else:
                # Rule is tracked but has fewer jobs than expected (some produced no log)
                existing = len(current[rule])
                for i in range(existing, count):
                    current[rule][f"_job_{i + 1}"] = {"state": DONE, "start": now, "end": now}
    return current


# ── rich rendering ────────────────────────────────────────────────────────────

_STATUS_ICON = {
    RUNNING: ("🔄 Run", "bold yellow"),
    DONE: ("✅ Done", "bold green"),
    FAILED: ("❌ Fail", "bold red"),
    WAITING: ("⏳ Wait", "dim"),
}

_SAMPLE_ICON = {
    RUNNING: "🔄",
    DONE: "✅",
    FAILED: "❌",
    WAITING: "⏳",
}


def _build_display(
    pipeline_name: str,
    version: str,
    expected: dict,
    current: dict,
    start_time: float,
    pid: int,
    memory_peaks: "dict | None" = None,
) -> Group:
    now = time.time()
    elapsed = now - start_time

    # ── totals ───────────────────────────────────────────────────────────────
    total_expected = sum(expected.values()) if expected else max(sum(len(v) for v in current.values()), 1)
    total_done = sum(1 for rv in current.values() for j in rv.values() if j["state"] == DONE)
    total_running = sum(1 for rv in current.values() for j in rv.values() if j["state"] == RUNNING)
    total_failed = sum(1 for rv in current.values() for j in rv.values() if j["state"] == FAILED)

    # cap at 100%: dryrun counts may diverge slightly from actual tracked jobs
    pct = min(100, int(100 * total_done / total_expected)) if total_expected else 0
    display_done = min(total_done, total_expected)
    bar_filled = int(18 * pct / 100)
    bar_str = "█" * bar_filled + "░" * (18 - bar_filled)

    ram = _ram_gb(pid) if pid else 0.0

    eta_str = "—"
    if 0 < total_done < total_expected and elapsed > 0:
        rate = total_done / elapsed
        eta_str = f"~{_elapsed_str((total_expected - total_done) / rate)}"

    # ── header ───────────────────────────────────────────────────────────────
    hdr = Text()
    hdr.append(f"\n 🧬 Sequana {pipeline_name} Pipeline", style="bold cyan")
    if version:
        hdr.append(f" v{version}", style="dim cyan")
    hdr.append("\n ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    hdr.append(f"\n 📊 Overall Progress  ")
    hdr.append(f"{pct:>3d}% ", style="bold yellow")
    hdr.append(bar_str, style="green")
    hdr.append(f"  {display_done}/{total_expected} jobs\n")
    hdr.append(f" ⏱  Elapsed: {_elapsed_str(elapsed)}")
    hdr.append(f"  │  ETA: {eta_str}")
    if ram > 0:
        hdr.append(f"  │  Peak RAM: {ram:.1f} GB")
    hdr.append("\n")

    # ── table ────────────────────────────────────────────────────────────────
    show_mem = _HAS_PSUTIL and memory_peaks is not None
    tbl = Table(box=box.ROUNDED, show_header=True, header_style="bold blue", expand=True)
    tbl.add_column("  Step", no_wrap=True, min_width=30)
    tbl.add_column("Samples", justify="center", min_width=16)
    tbl.add_column("Status", justify="center", min_width=10)
    tbl.add_column("Time", justify="right", min_width=10)
    if show_mem:
        tbl.add_column("Mem Peak", justify="right", min_width=9)

    # merge expected (which may include rules not yet started) with observed
    all_rules = list(expected.keys()) if expected else []
    for rule in current:
        if rule not in all_rules:
            all_rules.append(rule)

    for i, rule in enumerate(all_rules):
        rule_jobs = current.get(rule, {})
        rule_expected_n = expected.get(rule, len(rule_jobs))
        n_done = sum(1 for j in rule_jobs.values() if j["state"] == DONE)
        n_fail = sum(1 for j in rule_jobs.values() if j["state"] == FAILED)
        n_run = sum(1 for j in rule_jobs.values() if j["state"] == RUNNING)
        n_total = max(len(rule_jobs), rule_expected_n)

        # rule-level status
        if n_fail > 0:
            rule_status_key = FAILED
        elif n_run > 0:
            rule_status_key = RUNNING
        elif n_done == n_total and n_total > 0:
            rule_status_key = DONE
        elif n_done > 0:
            rule_status_key = RUNNING  # partial progress: some done, next batch not yet started
        else:
            rule_status_key = WAITING

        status_label, status_style = _STATUS_ICON[rule_status_key]
        status_text = Text(status_label, style=status_style)

        # sample progress bar
        bar_w = 8
        filled = int(bar_w * n_done / n_total) if n_total else 0
        s_bar = "█" * filled + "░" * (bar_w - filled)
        sample_str = f"{n_done}/{n_total}  {s_bar}"

        # rule timing — show the slowest sample; exclude synthetic _job_N placeholders
        monitor_start_dt = datetime.fromtimestamp(start_time)
        durations = [
            (j["end"] - j["start"]).total_seconds()
            for s, j in rule_jobs.items()
            if j["state"] == DONE and j["end"] and j["start"] >= monitor_start_dt and not s.startswith("_job_")
        ]
        if durations:
            time_str = _elapsed_str(max(durations))
        elif n_run > 0:
            running_s = [
                (datetime.now() - j["start"]).total_seconds() for j in rule_jobs.values() if j["state"] == RUNNING
            ]
            time_str = (_elapsed_str(max(running_s)) + "...") if running_s else "—"
        else:
            time_str = "—"

        mem_peak = (memory_peaks or {}).get(rule, 0.0)
        mem_str = f"{mem_peak:.1f} GB" if (show_mem and mem_peak > 0) else ("—" if show_mem else None)
        row = [f"  {i + 1}. {rule}", sample_str, status_text, time_str]
        if show_mem:
            row.append(mem_str)
        tbl.add_row(*row)

        # per-sample sub-rows only while the rule is active or failed
        # (collapse once all samples are done)
        # Exclude synthetic placeholder entries added for untracked rules
        visible_samples = [(s, j) for s, j in rule_jobs.items() if not s.startswith("_job_")]
        if rule_status_key in (RUNNING, FAILED):
            samples = visible_samples
            # also add queued placeholders up to expected count
            queued_n = rule_expected_n - len(samples)
            for sample, job in samples:
                icon = _SAMPLE_ICON[job["state"]]
                if job["state"] == DONE and job["end"]:
                    s_time = _elapsed_str((job["end"] - job["start"]).total_seconds())
                elif job["state"] == RUNNING:
                    s_time = _elapsed_str((datetime.now() - job["start"]).total_seconds()) + "..."
                elif job["state"] == FAILED:
                    s_time = "failed"
                else:
                    s_time = "queued"
                prefix = "└─" if (sample == samples[-1][0] and queued_n == 0) else "├─"
                sub_row = [f"     {prefix} {sample}", "", icon, s_time]
                if show_mem:
                    sub_row.append("")
                tbl.add_row(*sub_row, style="dim" if job["state"] == DONE else None)
            for _ in range(min(queued_n, 3)):
                extra = [""] if show_mem else []
                tbl.add_row("     ├─ …", "", "⏳", "queued", *extra, style="dim")

    # ── footer ───────────────────────────────────────────────────────────────
    ftr = Text()
    ftr.append(f"\n ⚡ Active: {total_running} jobs")
    ftr.append(f"  │  Completed: {total_done}")
    failed_style = "bold red" if total_failed else None
    ftr.append(f"  │  Failed: {total_failed}", style=failed_style)
    ftr.append(f"\n 📂 Working dir: {os.getcwd()}")
    ftr.append(f"\n 📋 Logs: logs/  │  Snakemake log: .sequana/snakemake.log")
    ftr.append("\n")

    return Group(hdr, tbl, ftr)


# ── public entry point ────────────────────────────────────────────────────────


def run_monitor(
    snakefile: str,
    profile: str,
    pipeline_name: str = "Pipeline",
    version: str = "",
    workdir: str = ".",
) -> int:
    """Run snakemake with a rich live progress display.

    Returns snakemake's exit code.
    Falls back to a plain subprocess exec if stdout is not a TTY.
    """
    workdir_path = Path(workdir).resolve()
    snakelog = workdir_path / ".sequana" / "snakemake.log"
    snakelog.parent.mkdir(parents=True, exist_ok=True)

    if not sys.stdout.isatty():
        # Non-interactive: just run snakemake directly and let it print normally
        cmd = ["snakemake", "-s", snakefile, "--profile", profile]
        return subprocess.run(cmd, cwd=workdir_path).returncode

    expected, log_to_job = _parse_dryrun(snakefile, profile, workdir_path)

    cmd = ["snakemake", "-s", snakefile, "--profile", profile]
    with open(snakelog, "w") as log_fh:
        proc = subprocess.Popen(cmd, cwd=workdir_path, stdout=log_fh, stderr=log_fh)

    pid = proc.pid
    start_time = time.time()
    current: dict = {}
    sm_current: dict = {}  # state from snakemake log (fallback for no-log rules)
    prev_merged: dict = {}  # merged state from previous scan, for transition detection
    memory_peaks: dict = {}  # rule → peak GB seen while any sample was RUNNING
    console = Console()

    def _handle_sigint(sig, frame):
        proc.send_signal(signal.SIGINT)

    signal.signal(signal.SIGINT, _handle_sigint)

    def _merged_scan():
        """Return merged state: log-file entries take precedence, but snakemake-log
        RUNNING state prevents premature DONE from a stale log-file mtime (e.g. a
        tool like flye that writes nothing to stdout/stderr during its main work).
        Timing is captured at the RUNNING→DONE transition in merged state so that
        the elapsed time reflects the true wall-clock duration seen by the monitor."""
        nonlocal current, sm_current, prev_merged
        current = _scan_logs(workdir_path, current, log_to_job)
        sm_current = _scan_snakemake_log(snakelog, sm_current)
        merged = dict(sm_current)  # start with snakemake-log state
        for rule, jobs in current.items():
            # If snakemake-log still shows RUNNING jobs for this rule, don't let
            # a stale log-file mtime mark any job as DONE prematurely.
            sm_rule_running = any(j["state"] == RUNNING for j in sm_current.get(rule, {}).values())
            if sm_rule_running:
                corrected = {
                    s: ({**j, "state": RUNNING, "end": None} if j["state"] == DONE else j) for s, j in jobs.items()
                }
                merged[rule] = corrected
            else:
                merged[rule] = jobs

        # Fix timing: when a job transitions RUNNING→DONE in the merged view,
        # stamp end=now and carry forward the start from the RUNNING entry.
        # This avoids using filesystem mtime/ctime which are unreliable on Linux
        # (ctime≈mtime, so end-start≈0 when derived from log-file metadata alone).
        now_dt = datetime.now()
        for rule, jobs in merged.items():
            for sample, job in jobs.items():
                prev_job = prev_merged.get(rule, {}).get(sample)
                if job["state"] == DONE:
                    if prev_job and prev_job["state"] == RUNNING:
                        # First cycle where this job appears DONE: lock in timing now
                        job["end"] = now_dt
                        job["start"] = prev_job["start"]
                    elif prev_job and prev_job["state"] == DONE and prev_job.get("end"):
                        # Already had a locked end time: preserve it
                        job["end"] = prev_job["end"]
                        job["start"] = prev_job["start"]

        prev_merged = {r: {s: dict(j) for s, j in rj.items()} for r, rj in merged.items()}
        return merged

    def _update_memory_peaks(display_state: dict, ram_now: float) -> None:
        """For every rule with at least one RUNNING job, update its peak RAM."""
        if not _HAS_PSUTIL or ram_now <= 0:
            return
        for rule, jobs in display_state.items():
            if any(j["state"] == RUNNING for j in jobs.values()):
                memory_peaks[rule] = max(memory_peaks.get(rule, 0.0), ram_now)

    with Live(console=console, refresh_per_second=2, screen=False) as live:
        while proc.poll() is None:
            display_state = _merged_scan()
            ram_now = _ram_gb(pid)
            _update_memory_peaks(display_state, ram_now)
            live.update(_build_display(pipeline_name, version, expected, display_state, start_time, pid, memory_peaks))
            time.sleep(0.1)

        # final scan after process exits
        display_state = _merged_scan()
        current = display_state  # keep reference for _mark_remaining_*
        returncode = proc.returncode
        if returncode != 0:
            current = _mark_remaining_failed(current)
        else:
            current = _mark_remaining_done(current, expected)
        live.update(_build_display(pipeline_name, version, expected, current, start_time, None, memory_peaks))

    if returncode != 0:
        console.print(
            f"\n[bold red]Pipeline failed (exit {returncode}).[/bold red] " f"See [dim]{snakelog}[/dim] for details."
        )
        try:
            from rich.panel import Panel

            from sequana_pipetools.diagnose import _sequana_tips

            log_context = snakelog.read_text(errors="replace") if snakelog.exists() else ""
            tips = _sequana_tips(log_context, workdir_path).lstrip("\n-").strip()
            console.print(Panel(tips, title="💡 Sequana tips", border_style="bold green", padding=(1, 2)))
        except Exception:
            pass
    else:
        total_done = sum(1 for rv in current.values() for j in rv.values() if j["state"] == DONE)
        elapsed = time.time() - start_time
        from rich.panel import Panel

        console.print(
            f"\n[bold green]✅ Pipeline completed successfully.[/bold green] "
            f"{total_done} jobs in {_elapsed_str(elapsed)}."
        )
        console.print(Panel(CITATION_MESSAGE, title="Citation", border_style="bold cyan", padding=(1, 2)))
        summary = workdir_path / "summary.html"
        if summary.exists():
            from rich.panel import Panel

            console.print(
                Panel(
                    f"Open the summary report: [cyan]{summary}[/cyan]",
                    title="✅ Pipeline completed",
                    border_style="bold green",
                    padding=(1, 2),
                )
            )

    return returncode
