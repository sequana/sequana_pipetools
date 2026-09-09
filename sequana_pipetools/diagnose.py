"""LLM-powered diagnosis of Sequana pipeline failures.

Scans the snakemake log and failed rule logs in a pipeline working directory,
then asks an LLM to explain the errors in plain language.

Supported providers
-------------------
mistral  (default) – free tier available, requires MISTRAL_API_KEY
                      https://console.mistral.ai/
openai             – paid account required, requires OPENAI_API_KEY
                      https://platform.openai.com/
local              – any OpenAI-compatible server (Ollama, vLLM, llama.cpp,
                      LM Studio, an institutional gateway). No API key and no
                      internet access needed when the server runs locally.
                      Defaults to Ollama on http://localhost:11434/v1 ; use
                      --base-url (or OPENAI_BASE_URL) for another endpoint.
"""

from __future__ import annotations

import os
import re
import time
from functools import partial
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

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
    lines = [line for line in text.splitlines() if not _NOISE_LINE_RE.search(line)]
    return "\n".join(lines)


_PROVIDERS = ("mistral", "openai", "local")
_DEFAULT_MODELS = {
    "mistral": "mistral-small-latest",
    "openai": "gpt-4o-mini",
    "local": "llama3.2",
}

# Providers reached through the OpenAI-compatible chat/completions API
_OPENAI_COMPATIBLE = ("openai", "local")

# Endpoint used by the 'local' provider when neither --base-url nor
# OPENAI_BASE_URL is set. This is the default Ollama address.
_DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"


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
            "  export MISTRAL_API_KEY=<your-key>\n"
            "Or run a model locally instead, with no key and no internet access:\n"
            "  ollama pull llama3.2      (see https://ollama.com)\n"
            "  sequana_pipetools --diagnose --provider local"
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


def _call_openai(context: str, model: str, base_url: str | None = None) -> str:
    """Query an OpenAI-compatible chat/completions endpoint.

    *base_url* selects the server. ``None`` means the official OpenAI API and an
    ``OPENAI_API_KEY`` is then mandatory. Any other value (Ollama, vLLM,
    llama.cpp, an institutional gateway) usually ignores the key, so a
    placeholder is used when the variable is not set.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for the openai and local providers.\n"
            "Install it with:  pip install sequana_pipetools[ai-openai]  or  pip install openai"
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        if base_url:
            # local/self-hosted servers require no credential but the SDK asks for one
            api_key = "no-key-required"
        else:
            raise EnvironmentError(
                "OPENAI_API_KEY environment variable is not set.\n"
                "Export your key:  export OPENAI_API_KEY=sk-...\n"
                "Or run a model locally instead, with no key and no internet access:\n"
                "  ollama pull llama3.2      (see https://ollama.com)\n"
                "  sequana_pipetools --diagnose --provider local"
            )

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Here are the pipeline logs:\n\n{context}"},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content


# ── error handling and retries ────────────────────────────────────────────────


class DiagnoseError(Exception):
    """Raised when the LLM backend could not produce a diagnosis."""


# Number of attempts (first call included) when the provider rate-limits us
_MAX_ATTEMPTS = 3

# Base delay in seconds for the exponential backoff between two attempts
_RETRY_BASE_DELAY = 5.0

_RATE_LIMIT_RE = re.compile(r"\b429\b|rate.?limit", re.IGNORECASE)


def _status_code(err: Exception):
    """Best-effort extraction of an HTTP status code from a provider SDK exception."""
    candidates = [getattr(err, attr, None) for attr in ("status_code", "http_status", "raw_status_code")]
    candidates.append(getattr(getattr(err, "response", None), "status_code", None))
    for value in candidates:
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _is_rate_limit(err: Exception) -> bool:
    """Return True if *err* looks like a provider rate-limit (HTTP 429) error."""
    if _status_code(err) == 429:
        return True
    return bool(_RATE_LIMIT_RE.search(str(err)))


def _retry_after(err: Exception):
    """Return the Retry-After delay (seconds) advertised by the provider, if any."""
    headers = getattr(getattr(err, "response", None), "headers", None) or getattr(err, "headers", None)
    try:
        value = headers.get("Retry-After") or headers.get("retry-after")
    except AttributeError:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_base_url(provider: str, base_url: str | None = None) -> str | None:
    """Return the endpoint to query for *provider*.

    Explicit *base_url* wins, then the ``OPENAI_BASE_URL`` environment variable,
    then the provider default (Ollama for ``local``, the official API otherwise).
    """
    base_url = base_url or os.environ.get("OPENAI_BASE_URL")
    if not base_url and provider == "local":
        base_url = _DEFAULT_LOCAL_BASE_URL
    return base_url


def local_server_available(base_url: str | None = None, timeout: float = 1.0) -> bool:
    """Return True if an OpenAI-compatible server answers at *base_url*.

    Used to tell the user that ``--provider local`` would work when the remote
    provider failed. Defaults to the Ollama endpoint.
    """
    url = (base_url or _DEFAULT_LOCAL_BASE_URL).rstrip("/") + "/models"
    try:
        # nosec B310: user-provided base_url for local LLM server probing; endpoint
        # is trusted by design (user explicitly specifies it via CLI/env). Exceptions
        # are caught safely; function only checks server response, never executes it.
        with urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (URLError, OSError, ValueError):
        return False


def _call_provider(
    provider: str,
    context: str,
    model: str,
    base_url: str | None = None,
    max_attempts: int = _MAX_ATTEMPTS,
) -> str:
    """Call *provider* retrying on rate-limit errors, and never leak an SDK traceback.

    Missing package (ImportError) and missing API key (EnvironmentError) are raised
    as-is since retrying cannot help. Any other provider failure is wrapped into a
    :class:`DiagnoseError` carrying an actionable message.
    """
    if provider == "mistral":
        call = partial(_call_mistral, context, model)
    elif provider in _OPENAI_COMPATIBLE:
        call = partial(_call_openai, context, model, base_url=base_url)
    else:
        raise ValueError(f"Unknown provider: {provider}. Must be one of {_PROVIDERS}.")

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return call()
        except (ImportError, EnvironmentError):
            raise
        except Exception as err:  # SDK-specific exception classes, imported lazily
            last_error = err
            if not _is_rate_limit(err):
                message = f"The {provider} API call failed: {err}"
                if base_url:
                    message += (
                        f"\nEndpoint used: {base_url}\n"
                        "Check that the server is running and serves an OpenAI-compatible API "
                        "(for Ollama: `ollama serve` then `ollama pull " + model + "`)."
                    )
                raise DiagnoseError(message) from None
            if attempt == max_attempts:
                break
            delay = _retry_after(err) or _RETRY_BASE_DELAY * 2 ** (attempt - 1)
            logger.warning(
                f"{provider} rate limit reached (attempt {attempt}/{max_attempts}). Retrying in {delay:.0f}s."
            )
            time.sleep(delay)

    # Suggest alternatives based on which provider failed
    alternatives = [p for p in _PROVIDERS if p != provider]
    alt_text = f"or try --provider {alternatives[0]}" if alternatives else "or try a different API key"

    raise DiagnoseError(
        f"The {provider} API is rate-limiting this account (HTTP 429) and did not recover "
        f"after {max_attempts} attempts.\n"
        f"Wait a few minutes, use another API key, {alt_text}.\n"
        "The Sequana tips below require no API call."
    ) from None


# ── Sequana-specific post-processing ──────────────────────────────────────────

# Matches "fastp: command not found" and "/bin/bash: fastp: command not found"
# Group 1 = the tool name (last word before ": command not found")
_CMD_NOT_FOUND_RE = re.compile(
    r"(\w[\w.-]*):\s+command not found" r"|[Cc]ommand ['\"](\w[\w.-]*)['\"] not found",
    re.IGNORECASE,
)
_EXIT_127_RE = re.compile(r"exit(?:ed with)? (?:status )?127", re.IGNORECASE)


def _first_group(match: "re.Match") -> str:
    """Return the first non-empty capturing group of *match*, or an empty string."""
    for group in match.groups():
        if group:
            return group
    return ""


def _missing_input_tip(match: "re.Match") -> str:
    rule = _first_group(match)
    target = f" of rule `{rule}`" if rule else ""
    return (
        f"• Snakemake could not find the input files{target}. Check `input_directory` and `input_pattern`"
        " in config.yaml, and that the read tag matches your file names (e.g. _R[12]_)."
    )


def _incomplete_files_tip(match: "re.Match") -> str:
    return (
        "• Some output files are incomplete because a previous run was interrupted. Re-run with"
        " `--rerun-incomplete` added to the snakemake command in the launcher script."
    )


# Deterministic error signatures scanned in the collected logs. Each entry is a
# (compiled regex, message) pair where the message is either a literal string or
# a callable taking the match object. They require no LLM, so they are also the
# fallback when no provider can be reached. Order defines the display order.
_ERROR_SIGNATURES = (
    (
        re.compile(r"MissingInputException|Missing input files for rule (\w+)", re.IGNORECASE),
        _missing_input_tip,
    ),
    (
        re.compile(r"IncompleteFilesException|incomplete files|--rerun-incomplete", re.IGNORECASE),
        _incomplete_files_tip,
    ),
    (
        re.compile(r"Missing files after \d+ seconds|Not all output files.*were present", re.IGNORECASE),
        "• A rule finished without producing its output. Look at the matching `logs/<rule>/<sample>.log`;"
        " on a shared filesystem, a larger `--latency-wait` may also be needed.",
    ),
    (
        re.compile(
            r"oom.?kill|out of memory|OUT_OF_MEMORY|memory limit|exit(?:ed with)? (?:status )?137", re.IGNORECASE
        ),
        "• The job ran out of memory. Increase the memory in your SLURM profile"
        " (`.sequana/profile_slurm/config.yaml`) or add `--resources mem_mb=<value>`.",
    ),
    (
        re.compile(r"DUE TO TIME LIMIT|\bTIMEOUT\b|time limit exceeded", re.IGNORECASE),
        "• The job was killed by SLURM when it reached its walltime. Raise the time limit in"
        " `.sequana/profile_slurm/config.yaml` and re-submit.",
    ),
    (
        re.compile(r"No space left on device|Disk quota exceeded", re.IGNORECASE),
        "• The filesystem is full or your quota is exhausted. Free some space, or move the working"
        " directory to a scratch partition, then re-run.",
    ),
    (
        re.compile(r"Permission denied", re.IGNORECASE),
        "• A file or directory could not be read or written. Check the permissions of the working"
        " directory and of the input files (symlinks included).",
    ),
    (
        re.compile(r"pykwalify|SchemaError|does not comply|schema.*validation", re.IGNORECASE),
        "• The config file does not comply with the pipeline schema. Fix the reported key in"
        " config.yaml; `sequana_pipetools --config-to-schema` shows the expected structure.",
    ),
    (
        re.compile(
            r"(?:FATAL|failed|error).*(?:singularity|apptainer)"
            r"|(?:singularity|apptainer).*(?:FATAL|failed|error)"
            r"|Failed to pull|md5.*mismatch",
            re.IGNORECASE,
        ),
        "• A container image could not be downloaded or verified. Re-run the setup command; use"
        " `--apptainer-prefix <dir>` to reuse a shared image directory.",
    ),
    (
        re.compile(r"LockException|Directory cannot be locked|locked by another", re.IGNORECASE),
        "• The working directory is locked by an interrupted run. Unlock it before re-running.",
    ),
)


def _detect_error_signatures(context: str) -> list:
    """Return the tips matching the known error signatures found in *context*."""
    tips = []
    for regex, message in _ERROR_SIGNATURES:
        match = regex.search(context)
        if not match:
            continue
        tips.append(message(match) if callable(message) else message)
    return tips


def _detect_missing_tools(context: str) -> list:
    """Return a deduplicated list of tool names detected as missing in *context*."""
    tools = []
    for m in _CMD_NOT_FOUND_RE.finditer(context):
        tool = m.group(1) or m.group(2)
        if tool and tool not in tools:
            tools.append(tool)
    return tools


def _sequana_tips(context: str, workdir: Path, show_diagnose_tip: bool = True) -> str:
    """Build the Sequana tips block appended after the LLM output.

    Detected issues come first (they are specific to the failure at hand), then the
    generic reminders that apply to every run. Everything here is deterministic, so
    this block is also what is shown when no LLM provider can be reached.
    """
    lines = ["\n---"]

    # detected issues — specific to this failure, so they come first
    tools = _detect_missing_tools(context)
    for tool in tools:
        lines.append(f"• Missing tool detected: `damona install {tool}`")
    lines.extend(_detect_error_signatures(context))

    sh_files = [p.name for p in workdir.glob("*.sh") if not p.name.startswith(".")]

    # re-run instruction
    if sh_files:
        sh_name = sh_files[0]
        lines.append(f"• Once errors are corrected, re-run the pipeline: `sh {sh_name}`")
    else:
        lines.append("• Once errors are corrected, re-run the pipeline: `sh <pipeline_name>.sh`")

    # apptainer tip — always shown
    lines.append(
        "• To avoid tool installation issues, use container images: "
        "add `--apptainer-prefix ~/images` to your setup command."
    )

    # snakemake log tip — always shown
    lines.append("• Full snakemake output is in `.sequana/snakemake.log` if the terminal was truncated.")

    # unlock tip — always shown
    unlock_cmd = "sh unlock.sh" if (workdir / "unlock.sh").exists() else "snakemake --unlock"
    lines.append(f"• If snakemake reports a locked directory, unlock it with: `{unlock_cmd}`")

    # diagnose tip — suppressed when already running --diagnose
    if show_diagnose_tip:
        lines.append(
            "• For an AI-powered diagnosis, set `export MISTRAL_API_KEY=<your-key>` and run:\n"
            "  `sequana_pipetools --diagnose`\n"
            "  No API key? Install ollama, then: `ollama pull llama3.2` and"
            " `sequana_pipetools --diagnose --provider local`"
        )

    return "\n".join(lines)


# ── public entry point ────────────────────────────────────────────────────────


def diagnose(
    workdir: str = ".", provider: str = "mistral", model: str | None = None, base_url: str | None = None
) -> str:
    """Collect pipeline logs and return an LLM diagnosis string.

    Parameters
    ----------
    workdir:
        Pipeline working directory (default: current directory).
    provider:
        LLM provider: ``"mistral"`` (default, free tier), ``"openai"`` or
        ``"local"`` (any OpenAI-compatible server, no API key needed).
    model:
        Model name. Defaults to ``mistral-small-latest`` for Mistral,
        ``gpt-4o-mini`` for OpenAI and ``llama3.2`` for a local server.
    base_url:
        OpenAI-compatible endpoint to query (e.g. ``http://localhost:11434/v1``
        for Ollama). Defaults to the ``OPENAI_BASE_URL`` environment variable,
        then to the provider default. Ignored by the mistral provider.

    Returns
    -------
    str
        The LLM's diagnosis text.

    Raises
    ------
    DiagnoseError
        If the provider could not be reached or kept rate-limiting the request.
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. Choose from: {', '.join(_PROVIDERS)}")

    if model is None:
        model = _DEFAULT_MODELS[provider]

    workdir_path = Path(workdir).resolve()
    context = collect_context(workdir_path)

    result = _call_provider(provider, context, model, base_url=resolve_base_url(provider, base_url))

    return result + _sequana_tips(context, workdir_path, show_diagnose_tip=False)


def tips_only(workdir: str = ".") -> str:
    """Return the deterministic Sequana tips for *workdir*, without calling any LLM.

    Used as a fallback when the LLM provider is unreachable or rate-limiting.
    """
    workdir_path = Path(workdir).resolve()
    context = collect_context(workdir_path)
    return _sequana_tips(context, workdir_path, show_diagnose_tip=False)
