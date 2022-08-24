""" Setting up profile to setup """
import importlib.resources as pkg_resources
from pathlib import Path


def create_profile(workdir: Path, profile: str, **kwargs) -> str:
    """Create profile config in working directory."""
    with pkg_resources.path("sequana_pipetools.resources", f"{profile}.yaml") as slurm_file:
        slurm_text = slurm_file.read_text().format(**kwargs)
    outfile = workdir / f".sequana/profile_{profile}" / "config.yaml"
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(slurm_text)
    return f".sequana/profile_{profile}"
