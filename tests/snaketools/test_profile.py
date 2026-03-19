from pathlib import Path
from unittest.mock import patch

import pytest

from sequana_pipetools.snaketools.profile import (
    _build_local_config_v8,
    _build_slurm_config_v8,
    _create_profile_v7,
    _create_profile_v8,
    _is_v8,
    _snakemake_version,
    _write_yaml,
    create_profile,
)


def _base_kwargs():
    return {
        "jobs": 4,
        "wrappers": "https://raw.github.com/sequana/sequana-wrappers/",
        "forceall": False,
        "keep_going": False,
        "use_apptainer": False,
        "apptainer_prefix": "",
        "apptainer_args": "",
    }


# ── version detection ─────────────────────────────────────────────────────────


def test_snakemake_version_returns_tuple():
    v = _snakemake_version()
    assert isinstance(v, tuple)
    assert len(v) == 3
    assert all(isinstance(x, int) for x in v)


def test_is_v8_true():
    with patch("sequana_pipetools.snaketools.profile._snakemake_version", return_value=(8, 0, 0)):
        assert _is_v8() is True


def test_is_v8_false():
    with patch("sequana_pipetools.snaketools.profile._snakemake_version", return_value=(7, 32, 4)):
        assert _is_v8() is False


# ── v8 config builders ────────────────────────────────────────────────────────


def test_build_local_config_v8_defaults():
    config = _build_local_config_v8(**_base_kwargs())
    assert config["cores"] == 4
    assert config["keep-going"] is False
    assert config["forceall"] is False
    assert "wrapper-prefix" in config


def test_build_local_config_v8_keep_going():
    kwargs = _base_kwargs()
    kwargs["keep_going"] = True
    assert _build_local_config_v8(**kwargs)["keep-going"] is True


def test_build_local_config_v8_no_apptainer():
    config = _build_local_config_v8(**_base_kwargs())
    assert "software-deployment-method" not in config


def test_build_slurm_config_v8():
    kwargs = _base_kwargs()
    kwargs.update({"partition": "common", "qos": "normal", "memory": "4G"})
    config = _build_slurm_config_v8(**kwargs)
    assert config["executor"] == "cluster-generic"
    assert config["jobs"] == 4
    assert config["keep-going"] is False
    assert config["default-resources"]["partition"] == "common"


def test_build_slurm_config_v8_keep_going():
    kwargs = _base_kwargs()
    kwargs.update({"partition": "common", "qos": "normal", "memory": "4G", "keep_going": True})
    assert _build_slurm_config_v8(**kwargs)["keep-going"] is True


# ── _write_yaml ───────────────────────────────────────────────────────────────


def test_write_yaml(tmp_path):
    out = tmp_path / "config.yaml"
    _write_yaml(out, {"key": "value", "number": 42})
    content = out.read_text()
    assert "key" in content
    assert "value" in content
    assert "42" in content


# ── v7 profile creation ───────────────────────────────────────────────────────


def test_create_profile_v7_local(tmp_path):
    result = _create_profile_v7(tmp_path, "local", **_base_kwargs())
    assert result == ".sequana/profile_local"
    config_file = tmp_path / ".sequana" / "profile_local" / "config.yaml"
    assert config_file.exists()
    content = config_file.read_text()
    assert "cores" in content


def test_create_profile_v7_slurm(tmp_path):
    kwargs = _base_kwargs()
    kwargs.update({"partition": "common", "qos": "normal", "memory": "'4G'"})
    result = _create_profile_v7(tmp_path, "slurm", **kwargs)
    assert result == ".sequana/profile_slurm"
    assert (tmp_path / ".sequana" / "profile_slurm" / "config.yaml").exists()


# ── v8 profile creation ───────────────────────────────────────────────────────


def test_create_profile_v8_local(tmp_path):
    result = _create_profile_v8(tmp_path, "local", **_base_kwargs())
    assert result == ".sequana/profile_local"
    assert (tmp_path / ".sequana" / "profile_local" / "config.yaml").exists()


def test_create_profile_v8_slurm(tmp_path):
    kwargs = _base_kwargs()
    kwargs.update({"partition": "common", "qos": "normal", "memory": "4G"})
    result = _create_profile_v8(tmp_path, "slurm", **kwargs)
    assert result == ".sequana/profile_slurm"


def test_create_profile_v8_unsupported_profile(tmp_path):
    with pytest.raises(ValueError, match="Unsupported profile"):
        _create_profile_v8(tmp_path, "sge", **_base_kwargs())


# ── create_profile dispatcher ─────────────────────────────────────────────────


def test_create_profile_uses_v7(tmp_path):
    with patch("sequana_pipetools.snaketools.profile._is_v8", return_value=False):
        result = create_profile(tmp_path, "local", **_base_kwargs())
    assert "profile_local" in result


def test_create_profile_uses_v8(tmp_path):
    with patch("sequana_pipetools.snaketools.profile._is_v8", return_value=True):
        result = create_profile(tmp_path, "local", **_base_kwargs())
    assert "profile_local" in result
