from __future__ import annotations

"""LLM-powered diagnosis of Sequana pipeline failures.

Scans the snakemake log and failed rule logs in a pipeline working directory,
then asks an LLM to explain the errors in plain language.

Supported providers
-------------------
mistral  (default) – free tier available, requires MISTRAL_API_KEY
                      https://console.mistral.ai/
openai             – paid account required, requires OPENAI_API_KEY
                      https://platform.openai.com/
"""

import os
import re
from pathlib import Path

import colorlog

logger = colorlog.getLogger(__name__)

# Maximum number of log lines sent to the model to stay within token limits
_MAX_LOG_LINES = 150

# ANSI escape codes (substituted out, not line-dropped)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Whole-line noise patterns (lines matching these are dropped entirely)
_NOISE_LINE_RE = re.compile(
    r"slurm.*not found" r"|no.*slurm.*files",  # "No */*slurm*.out slurm files were found"
    re.IGNORECASE,
)


def _strip_noise(text: str) -> str:
    """Strip ANSI codes and drop lines that are known to mislead the LLM in local runs."""
    text = _ANSI_RE.sub("", text)
    lines = [l for l in text.splitlines() if not _NOISE_LINE_RE.search(l)]
    return "\n".join(lines)


_PROVIDERS = ("mistral", "openai")
_DEFAULT_MODELS = {
    "mistral": "mistral-small-latest",
    "openai": "gpt-4o-mini",
}


# ── log collection ────────────────────────────────────────────────────────────


def _read_tail(path: Path, max_lines: int) -> str:
    """Return up to *max_lines* lines from the end of *path*."""
    try:
        lines = path.read_text(errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])
    except OSError:
        return ""


def _find_snakemake_log(workdir: Path) -> "Path | None":
    """Return the best available snakemake log, in priority order:

    1. ``.sequana/snakemake.log`` — written by the tee redirect in runme.sh
    2. The most-recently-modified ``slurm-*.out`` at the workdir root — the
       main SLURM controller output produced when ``runme.sh`` was submitted
       via ``sbatch`` without a tee redirect (legacy runs).
    """
    p = workdir / ".sequana" / "snakemake.log"
    if p.exists():
        return p

    # Fallback: root-level slurm output files are the snakemake controller log
    # (per-rule job logs live under logs/<rule>/ and are handled separately).
    candidates = sorted(workdir.glob("slurm-*.out"), key=lambda f: f.stat().st_mtime)
    return candidates[-1] if candidates else None


def _extract_error_sections(text: str) -> str:
    """Keep only lines that look like errors / tracebacks to reduce noise."""
    keep = []
    in_traceback = False
    for line in text.splitlines():
        low = line.lower()
        if any(k in low for k in ("error", "exception", "traceback", "failed", "exited")):
            in_traceback = True
        if in_traceback:
            keep.append(line)
            if not line.strip():
                in_traceback = False
    # fallback: return last N lines if nothing matched
    return "\n".join(keep) if keep else "\n".join(text.splitlines()[-_MAX_LOG_LINES:])


def _find_failed_rule_logs(workdir: Path, snakemake_log_text: str) -> dict:
    """Return {label: log_content} for rules that appear to have failed."""
    failed: dict = {}

    # extract rule names from "Error in rule X:" or "rule X failed" patterns
    rule_names = re.findall(r"(?:Error in rule|rule)\s+(\w+)[\s:]", snakemake_log_text, re.IGNORECASE)
    rule_names = list(dict.fromkeys(rule_names))  # deduplicate, preserve order

    for rule in rule_names:
        # search common log locations: logs/<rule>/*.log and <sample>/<rule>/*.log
        candidates = list(workdir.rglob(f"**/{rule}/*.log")) + list(workdir.glob(f"logs/{rule}/*.log"))
        # skip hidden dirs
        candidates = [p for p in candidates if not any(part.startswith(".") for part in p.relative_to(workdir).parts)]
        for log_path in candidates[:3]:  # at most 3 per rule
            content = _read_tail(log_path, _MAX_LOG_LINES)
            if content.strip():
                failed[f"{rule} ({log_path.relative_to(workdir)})"] = content

    return failed


def collect_context(workdir: Path) -> str:
    """Build the full diagnostic context string to send to the LLM."""
    sections = []

    snakemake_log_path = _find_snakemake_log(workdir)
    snakemake_text = ""
    if snakemake_log_path:
        snakemake_text = _strip_noise(_read_tail(snakemake_log_path, _MAX_LOG_LINES))
        error_text = _extract_error_sections(snakemake_text)
        sections.append(f"## Snakemake log ({snakemake_log_path.relative_to(workdir)})\n{error_text}")
    else:
        sections.append("## Snakemake log\n(not found — run the pipeline first)")

    rule_logs = _find_failed_rule_logs(workdir, snakemake_text)
    for label, content in rule_logs.items():
        sections.append(f"## Rule log: {label}\n{content}")

    return "\n\n".join(sections)


# ── LLM prompt ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert in bioinformatics pipelines built with Snakemake and the \
Sequana framework. A user has run a Sequana pipeline that failed. \
Your job is to:
1. Identify the root cause of the failure from the logs provided.
2. Explain the error in plain, non-technical language.
3. Suggest concrete steps to fix it.
Keep your response concise (under 300 words) and actionable.\
"""


# ── provider backends ─────────────────────────────────────────────────────────


def _call_mistral(context: str, model: str) -> str:
    try:
        # mistralai >= 1.0 moved the client to mistralai.client in v2.x
        try:
            from mistralai.client import Mistral
        except ImportError:
            from mistralai import Mistral  # v1.x fallback
    except ImportError:
        raise ImportError(
            "The 'mistralai' package is required for the mistral provider.\n"
            "Install it with:  pip install sequana_pipetools[ai]  or  pip install mistralai"
        )

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "MISTRAL_API_KEY environment variable is not set.\n"
            "Get a free key at https://console.mistral.ai/ then:\n"
            "  export MISTRAL_API_KEY=<your-key>"
        )

    client = Mistral(api_key=api_key)
    response = client.chat.complete(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Here are the pipeline logs:\n\n{context}"},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content


def _call_openai(context: str, model: str) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for the openai provider.\n" "Install it with:  pip install openai"
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set.\n" "Export your key:  export OPENAI_API_KEY=sk-..."
        )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Here are the pipeline logs:\n\n{context}"},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content


# ── Sequana-specific post-processing ──────────────────────────────────────────

# Matches "fastp: command not found" and "/bin/bash: fastp: command not found"
# Group 1 = the tool name (last word before ": command not found")
_CMD_NOT_FOUND_RE = re.compile(
    r"(\w[\w.-]*):\s+command not found" r"|[Cc]ommand ['\"](\w[\w.-]*)['\"] not found",
    re.IGNORECASE,
)
_EXIT_127_RE = re.compile(r"exit(?:ed with)? (?:status )?127", re.IGNORECASE)


def _detect_missing_tools(context: str) -> list:
    """Return a deduplicated list of tool names detected as missing in *context*."""
    tools = []
    for m in _CMD_NOT_FOUND_RE.finditer(context):
        tool = m.group(1) or m.group(2)
        if tool and tool not in tools:
            tools.append(tool)
    return tools


def _sequana_tips(context: str, workdir: Path) -> str:
    """Build the unconditional Sequana tips block appended after the LLM output."""
    lines = ["\n---", "💡 **Sequana tips**\n"]

    # re-run instruction: find the pipeline .sh launcher
    sh_files = [p.name for p in workdir.glob("*.sh") if not p.name.startswith(".")]
    if sh_files:
        sh_name = sh_files[0]
        lines.append(f"  • **once done, re-run the pipeline**: `sh {sh_name}`")
    else:
        lines.append("  • **once done, re-run the pipeline**: `sh <pipeline_name>.sh`")

    # apptainer tip — always shown
    lines.append(
        "  • **Use container images** (avoids manual tool installs): "
        "re-run setup with `--apptainer-prefix ~/images`, e.g.:\n"
        "      `sequana_<pipeline> --apptainer-prefix ~/images [other options]`"
    )

    # missing-tool tip — only when a tool name can be identified
    tools = _detect_missing_tools(context)
    for tool in tools:
        lines.append(f"  • **Missing tool detected**: `damona install {tool}`")

    return "\n".join(lines)


# ── public entry point ────────────────────────────────────────────────────────


def diagnose(workdir: str = ".", provider: str = "mistral", model: str | None = None) -> str:
    """Collect pipeline logs and return an LLM diagnosis string.

    Parameters
    ----------
    workdir:
        Pipeline working directory (default: current directory).
    provider:
        LLM provider: ``"mistral"`` (default, free tier) or ``"openai"``.
    model:
        Model name. Defaults to ``mistral-small-latest`` for Mistral and
        ``gpt-4o-mini`` for OpenAI.

    Returns
    -------
    str
        The LLM's diagnosis text.
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. Choose from: {', '.join(_PROVIDERS)}")

    if model is None:
        model = _DEFAULT_MODELS[provider]

    workdir_path = Path(workdir).resolve()
    context = collect_context(workdir_path)

    if provider == "mistral":
        result = _call_mistral(context, model)
    else:
        result = _call_openai(context, model)

    return result + _sequana_tips(context, workdir_path)
