""" Setting up profile to setup """
import importlib.resources as pkg_resources
from pathlib import Path


def create_slurm_profile(
    workdir: Path,
    memory: str = "4G",
    jobs: str = "40",
    partition: str = "common",
    qos: str = "normal",
    wrappers: str = "https://github.com/sequana/sequana-wrappers/raw"
):
    with pkg_resources.path("sequana_pipetools.resources", "slurm.yaml") as slurm_file:
        slurm_text = slurm_file.read_text().format(
            memory=memory,
            jobs=jobs,
            partition=partition,
            qos=qos,
            wrappers=wrappers
        )
    outfile = workdir / "slurm" / "config.yaml"
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(slurm_text)
