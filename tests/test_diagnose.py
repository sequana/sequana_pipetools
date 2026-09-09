import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sequana_pipetools.diagnose import (
    DiagnoseError,
    _call_mistral,
    _call_openai,
    _call_provider,
    _detect_error_signatures,
    _detect_missing_tools,
    _extract_error_sections,
    _find_failed_rule_logs,
    _find_snakemake_log,
    _is_rate_limit,
    _read_tail,
    _retry_after,
    _sequana_tips,
    _strip_noise,
    collect_context,
    diagnose,
    resolve_base_url,
    tips_only,
)


def test_strip_noise_ansi():
    text = "\x1b[32mgreen\x1b[0m normal"
    result = _strip_noise(text)
    assert "\x1b" not in result
    assert "normal" in result


def test_strip_noise_removes_slurm_lines():
    text = "good line\nno slurm files found here\nanother good line"
    result = _strip_noise(text)
    assert "good line" in result
    assert "slurm files" not in result


def test_read_tail(tmp_path):
    f = tmp_path / "test.log"
    f.write_text("\n".join(str(i) for i in range(20)))
    result = _read_tail(f, max_lines=5)
    assert "19" in result
    assert result.count("\n") < 5


def test_read_tail_missing(tmp_path):
    assert _read_tail(tmp_path / "nonexistent.log", max_lines=10) == ""


def test_find_snakemake_log_present(tmp_path):
    log = tmp_path / ".sequana" / "snakemake.log"
    log.parent.mkdir()
    log.write_text("hello")
    assert _find_snakemake_log(tmp_path) == log


def test_find_snakemake_log_absent(tmp_path):
    assert _find_snakemake_log(tmp_path) is None


def test_extract_error_sections_with_errors():
    text = "Starting pipeline\nError: something failed\ntraceback detail\n\nnormal"
    result = _extract_error_sections(text)
    assert "Error" in result


def test_extract_error_sections_fallback():
    # No error keywords → falls back to last N lines
    lines = [f"line {i}" for i in range(200)]
    result = _extract_error_sections("\n".join(lines))
    assert "line 199" in result


def test_find_failed_rule_logs(tmp_path):
    log_dir = tmp_path / "logs" / "fastqc"
    log_dir.mkdir(parents=True)
    (log_dir / "sample1.log").write_text("error details\n")
    result = _find_failed_rule_logs(tmp_path, "Error in rule fastqc:")
    assert any("fastqc" in k for k in result)


def test_find_failed_rule_logs_no_match(tmp_path):
    result = _find_failed_rule_logs(tmp_path, "all fine, no errors")
    assert result == {}


def test_collect_context_no_log(tmp_path):
    context = collect_context(tmp_path)
    assert "not found" in context


def test_collect_context_with_log(tmp_path):
    log = tmp_path / ".sequana" / "snakemake.log"
    log.parent.mkdir()
    log.write_text("Error in rule fastqc:\n  job failed\n")
    log_dir = tmp_path / "logs" / "fastqc"
    log_dir.mkdir(parents=True)
    (log_dir / "s1.log").write_text("fastp: command not found\n")
    context = collect_context(tmp_path)
    assert "Snakemake log" in context
    assert "Rule log" in context


def test_detect_missing_tools_found():
    tools = _detect_missing_tools("fastp: command not found\nother line")
    assert "fastp" in tools


def test_detect_missing_tools_none():
    assert _detect_missing_tools("everything is fine") == []


def test_detect_missing_tools_deduplication():
    text = "fastp: command not found\nfastp: command not found"
    tools = _detect_missing_tools(text)
    assert tools.count("fastp") == 1


def test_sequana_tips_with_sh_file(tmp_path):
    (tmp_path / "pipeline.sh").write_text("#!/bin/bash\n")
    tips = _sequana_tips("", tmp_path)
    assert "pipeline.sh" in tips
    assert "apptainer" in tips.lower()


def test_sequana_tips_no_sh(tmp_path):
    tips = _sequana_tips("", tmp_path)
    assert "pipeline_name" in tips


def test_sequana_tips_missing_tool(tmp_path):
    tips = _sequana_tips("fastp: command not found", tmp_path)
    assert "fastp" in tips


def test_call_mistral_no_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    mock_module = MagicMock()
    with patch.dict("sys.modules", {"mistralai": mock_module, "mistralai.client": mock_module}):
        with pytest.raises(EnvironmentError, match="MISTRAL_API_KEY"):
            _call_mistral("context", "mistral-small-latest")


def test_call_mistral_success(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "diagnosis text"
    mock_client = MagicMock()
    mock_client.chat.complete.return_value = mock_response
    mock_cls = MagicMock(return_value=mock_client)
    mock_module = MagicMock()
    mock_module.Mistral = mock_cls
    with patch.dict("sys.modules", {"mistralai": mock_module, "mistralai.client": mock_module}):
        result = _call_mistral("context", "mistral-small-latest")
    assert result == "diagnosis text"


def test_call_openai_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    mock_module = MagicMock()
    with patch.dict("sys.modules", {"openai": mock_module}):
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            _call_openai("context", "gpt-4o-mini")


def test_call_openai_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "openai result"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_cls = MagicMock(return_value=mock_client)
    mock_module = MagicMock()
    mock_module.OpenAI = mock_cls
    with patch.dict("sys.modules", {"openai": mock_module}):
        result = _call_openai("context", "gpt-4o-mini")
    assert result == "openai result"


def test_diagnose_invalid_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        diagnose(provider="unknown_llm")


def test_diagnose_openai_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    with patch("sequana_pipetools.diagnose._call_openai", return_value="openai output"):
        result = diagnose(workdir=str(tmp_path), provider="openai")
    assert "openai output" in result


def test_diagnose_uses_default_model(tmp_path):
    with patch("sequana_pipetools.diagnose._call_mistral", return_value="ok") as mock:
        diagnose(workdir=str(tmp_path), provider="mistral")
    _, call_model = mock.call_args[0]
    assert call_model == "mistral-small-latest"


def test_diagnose_custom_model(tmp_path):
    with patch("sequana_pipetools.diagnose._call_mistral", return_value="ok") as mock:
        diagnose(workdir=str(tmp_path), provider="mistral", model="mistral-large-latest")
    _, call_model = mock.call_args[0]
    assert call_model == "mistral-large-latest"


class _SDKError(Exception):
    """Stand-in for a provider SDK exception carrying an HTTP status."""

    def __init__(self, message, status_code=None, headers=None):
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers


def test_is_rate_limit_from_status_code():
    assert _is_rate_limit(_SDKError("API error occurred", status_code=429))


def test_is_rate_limit_from_message():
    # mistralai raises a plain SDKError whose text carries the status
    assert _is_rate_limit(Exception('API error occurred: Status 429. Body: {"message":"Rate limit exceeded"}'))


def test_is_rate_limit_false():
    assert not _is_rate_limit(_SDKError("boom", status_code=500))


def test_retry_after_header():
    assert _retry_after(_SDKError("nope", status_code=429, headers={"Retry-After": "12"})) == 12.0


def test_retry_after_absent():
    assert _retry_after(_SDKError("nope", status_code=429)) is None


def test_call_provider_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("sequana_pipetools.diagnose.time.sleep", lambda delay: None)
    calls = []

    def flaky(context, model):
        calls.append(model)
        if len(calls) < 3:
            raise _SDKError("API error occurred: Status 429", status_code=429)
        return "recovered"

    with patch("sequana_pipetools.diagnose._call_mistral", side_effect=flaky):
        assert _call_provider("mistral", "context", "mistral-small-latest") == "recovered"
    assert len(calls) == 3


def test_call_provider_rate_limit_exhausted(monkeypatch):
    monkeypatch.setattr("sequana_pipetools.diagnose.time.sleep", lambda delay: None)
    err = _SDKError("API error occurred: Status 429", status_code=429)
    with patch("sequana_pipetools.diagnose._call_mistral", side_effect=err):
        with pytest.raises(DiagnoseError, match="rate-limiting"):
            _call_provider("mistral", "context", "mistral-small-latest")


def test_call_provider_other_error_not_retried():
    err = _SDKError("Status 500", status_code=500)
    with patch("sequana_pipetools.diagnose._call_mistral", side_effect=err) as mock:
        with pytest.raises(DiagnoseError, match="API call failed"):
            _call_provider("mistral", "context", "mistral-small-latest")
    assert mock.call_count == 1


def test_call_provider_missing_key_not_retried():
    with patch("sequana_pipetools.diagnose._call_mistral", side_effect=EnvironmentError("MISTRAL_API_KEY")) as mock:
        with pytest.raises(EnvironmentError):
            _call_provider("mistral", "context", "mistral-small-latest")
    assert mock.call_count == 1


def test_diagnose_raises_diagnose_error_on_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("sequana_pipetools.diagnose.time.sleep", lambda delay: None)
    err = _SDKError("API error occurred: Status 429", status_code=429)
    with patch("sequana_pipetools.diagnose._call_mistral", side_effect=err):
        with pytest.raises(DiagnoseError):
            diagnose(workdir=str(tmp_path), provider="mistral")


def test_tips_only(tmp_path):
    (tmp_path / "fastqc.sh").write_text("snakemake")
    result = tips_only(str(tmp_path))
    assert "sh fastqc.sh" in result
    assert "sequana_pipetools --diagnose" not in result


def test_resolve_base_url_local_default(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    assert resolve_base_url("local") == "http://localhost:11434/v1"


def test_resolve_base_url_openai_default(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    assert resolve_base_url("openai") is None


def test_resolve_base_url_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://gpu-node:8000/v1")
    assert resolve_base_url("openai") == "http://gpu-node:8000/v1"
    assert resolve_base_url("local") == "http://gpu-node:8000/v1"


def test_resolve_base_url_explicit_wins(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://from-env/v1")
    assert resolve_base_url("local", "http://explicit/v1") == "http://explicit/v1"


def test_diagnose_local_default_model(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with patch("sequana_pipetools.diagnose._call_openai", return_value="ok") as mock:
        diagnose(workdir=str(tmp_path), provider="local")
    assert mock.call_args[0][1] == "llama3.2"
    assert mock.call_args[1]["base_url"] == "http://localhost:11434/v1"


def test_call_openai_no_key_but_base_url(monkeypatch):
    """A local server needs no credential: the SDK placeholder must be used instead of raising."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "local result"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_cls = MagicMock(return_value=mock_client)
    mock_module = MagicMock()
    mock_module.OpenAI = mock_cls
    with patch.dict("sys.modules", {"openai": mock_module}):
        result = _call_openai("context", "llama3.2", base_url="http://localhost:11434/v1")
    assert result == "local result"
    assert mock_cls.call_args[1]["base_url"] == "http://localhost:11434/v1"
    assert mock_cls.call_args[1]["api_key"] == "no-key-required"


def test_call_provider_unreachable_server_message(monkeypatch):
    """A dead local endpoint must produce an actionable message, not a bare SDK error."""
    err = _SDKError("Connection error.")
    with patch("sequana_pipetools.diagnose._call_openai", side_effect=err):
        with pytest.raises(DiagnoseError, match="localhost:11434"):
            _call_provider("local", "context", "llama3.2", base_url="http://localhost:11434/v1")


@pytest.mark.parametrize(
    "log,expected",
    [
        ("MissingInputException in rule fastqc", "input_directory"),
        ("Missing input files for rule bwa_mem:", "rule `bwa_mem`"),
        ("IncompleteFilesException", "--rerun-incomplete"),
        ("Missing files after 5 seconds", "latency-wait"),
        ("slurmstepd: error: Detected 1 oom-kill event", "mem_mb"),
        ("JobId=42 State=OUT_OF_MEMORY", "mem_mb"),
        ("exited with status 137", "mem_mb"),
        ("CANCELLED AT 2026-01-01 DUE TO TIME LIMIT", "walltime"),
        ("OSError: [Errno 28] No space left on device", "quota"),
        ("Disk quota exceeded", "quota"),
        ("PermissionError: Permission denied: 'config.yaml'", "permissions"),
        ("pykwalify.errors.SchemaError: Cannot find required key", "schema"),
        ("FATAL: singularity image not found", "container image"),
        ("Directory cannot be locked", "Unlock"),
    ],
)
def test_detect_error_signatures(log, expected):
    tips = _detect_error_signatures(log)
    assert any(expected in tip for tip in tips), tips


def test_detect_error_signatures_clean_log():
    assert _detect_error_signatures("Finished job 0.\n1 of 1 steps (100%) done") == []


def test_detect_error_signatures_reports_each_once():
    log = "oom-kill event\nOut of memory\nOUT_OF_MEMORY\nexited with status 137"
    assert len(_detect_error_signatures(log)) == 1


def test_sequana_tips_lists_detected_issues_first(tmp_path):
    context = "slurmstepd: error: Detected 1 oom-kill event"
    lines = [line for line in _sequana_tips(context, tmp_path).splitlines() if line.startswith("•")]
    assert "mem_mb" in lines[0]


def test_local_server_available_when_down():
    from sequana_pipetools.diagnose import local_server_available

    # port 1 is never a valid LLM endpoint
    assert local_server_available("http://127.0.0.1:1/v1", timeout=0.5) is False
