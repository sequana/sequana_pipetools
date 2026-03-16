import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sequana_pipetools.diagnose import (
    _call_mistral,
    _call_openai,
    _detect_missing_tools,
    _extract_error_sections,
    _find_failed_rule_logs,
    _find_snakemake_log,
    _read_tail,
    _sequana_tips,
    _strip_noise,
    collect_context,
    diagnose,
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
