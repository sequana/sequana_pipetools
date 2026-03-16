"""Setting up Snakemake profiles.

Supports both snakemake v7 (template-based) and v8+ (programmatic, plugin-based).
"""

try:
    import importlib.resources as resources
except ImportError:  # pragma: no cover
    import importlib_resources as resources

from pathlib import Path

import colorlog

logger = colorlog.getLogger(__name__)


def _snakemake_version():
    """Return the installed snakemake version as a tuple (major, minor, patch)."""
    try:
        import snakemake

        parts = snakemake.__version__.split(".")
        return tuple(int(x) for x in parts[:3])
    except Exception:  # pragma: no cover
        return (7, 0, 0)


def _is_v8():
    return _snakemake_version()[0] >= 8


# ---------------------------------------------------------------------------
# v7 helpers (existing template approach)
# ---------------------------------------------------------------------------


def _create_profile_v7(workdir: Path, profile: str, **kwargs) -> str:
    """Create profile config using the legacy YAML template (snakemake < 8)."""
    try:
        profile_file = resources.files("sequana_pipetools.resources").joinpath(f"{profile}.yaml")
        with open(profile_file, "r") as fin:
            profile_text = fin.read()
            profile_text = profile_text.format(**kwargs)
    except AttributeError:  # pragma: no cover
        # python 3.8 back-compat
        with resources.path("sequana_pipetools.resources", f"{profile}.yaml") as profile_file:
            profile_text = profile_file.read_text().format(**kwargs)

    outfile = workdir / f".sequana/profile_{profile}" / "config.yaml"
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(profile_text)
    return f".sequana/profile_{profile}"


# ---------------------------------------------------------------------------
# v8 helpers (programmatic, executor-plugin based)
# ---------------------------------------------------------------------------


def _build_local_config_v8(**kwargs) -> dict:
    """Build a snakemake v8 local profile config dict."""
    config = {
        "keep-going": True,
        "printshellcmds": True,
        "cores": kwargs["jobs"],
        "wrapper-prefix": kwargs["wrappers"],
        "forceall": bool(kwargs.get("forceall", False)),
    }
    if kwargs.get("use_apptainer"):
        config["software-deployment-method"] = ["apptainer"]
        if kwargs.get("apptainer_args"):
            config["apptainer-args"] = kwargs["apptainer_args"]
        if kwargs.get("apptainer_prefix"):
            config["apptainer-prefix"] = str(kwargs["apptainer_prefix"])
    return config


def _build_slurm_config_v8(**kwargs) -> dict:
    """Build a snakemake v8 slurm profile config dict using cluster-generic plugin."""
    submit_cmd = (
        "mkdir -p logs/{rule} && "
        "sbatch "
        "--partition={resources.partition} "
        "--qos={resources.qos} "
        "--cpus-per-task={threads} "
        "--mem={resources.mem} "
        "--job-name=smk-{rule}-{wildcards} "
        "--output=logs/{rule}/{rule}-{wildcards}-slurm-%j.out "
        '$(bash -c \'[[ ! -z "{resources.gres}" ]] && echo "--gres={resources.gres}"\')'
    )
    config = {
        "executor": "cluster-generic",
        "cluster-generic-submit-cmd": submit_cmd,
        "default-resources": {
            "partition": kwargs["partition"],
            "qos": kwargs["qos"],
            "mem": kwargs["memory"],
            "gres": "",
        },
        "keep-going": True,
        "printshellcmds": True,
        "jobs": kwargs["jobs"],
        "wrapper-prefix": kwargs["wrappers"],
        "forceall": bool(kwargs.get("forceall", False)),
    }
    if kwargs.get("use_apptainer"):
        config["software-deployment-method"] = ["apptainer"]
        if kwargs.get("apptainer_args"):
            config["apptainer-args"] = kwargs["apptainer_args"]
        if kwargs.get("apptainer_prefix"):
            config["apptainer-prefix"] = str(kwargs["apptainer_prefix"])
    return config


def _write_yaml(outfile: Path, data: dict):
    """Write dict as YAML using ruamel.yaml (already a pipetools dependency)."""
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 2**16  # prevent long strings from being wrapped across lines
    with open(outfile, "w") as fout:
        yaml.dump(data, fout)


def _create_profile_v8(workdir: Path, profile: str, **kwargs) -> str:
    """Create profile config programmatically for snakemake v8+."""
    if profile == "local":
        config = _build_local_config_v8(**kwargs)
    elif profile == "slurm":
        config = _build_slurm_config_v8(**kwargs)
    else:  # pragma: no cover
        raise ValueError(f"Unsupported profile '{profile}' for snakemake v8. Use 'local' or 'slurm'.")

    outfile = workdir / f".sequana/profile_{profile}" / "config.yaml"
    outfile.parent.mkdir(parents=True, exist_ok=True)
    _write_yaml(outfile, config)
    return f".sequana/profile_{profile}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_profile(workdir: Path, profile: str, **kwargs) -> str:
    """Create a Snakemake profile config in the working directory.

    Automatically selects the correct format for the installed snakemake
    version:
    - snakemake < 8 : YAML template with legacy flags (use-singularity, etc.)
    - snakemake >= 8: programmatic config with executor plugins and renamed
      apptainer flags (software-deployment-method, apptainer-args, etc.)

    Returns the relative path of the profile directory.
    """
    if _is_v8():
        logger.debug("Detected snakemake >= 8, using v8 profile format")
        return _create_profile_v8(workdir, profile, **kwargs)
    else:
        logger.debug("Detected snakemake < 8, using legacy profile format")
        return _create_profile_v7(workdir, profile, **kwargs)
