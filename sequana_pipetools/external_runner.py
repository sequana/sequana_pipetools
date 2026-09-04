import html
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import rich_click as click

from sequana_pipetools.monitor import run_monitor
from sequana_pipetools.snaketools.dot_parser import convert_dot_to_png
from sequana_pipetools.snaketools.profile import create_profile


def _format_elapsed(seconds: float) -> str:
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes:d}m {seconds:02d}s"
    return f"{seconds:d}s"


def _get_snakemake_version() -> str:
    try:
        import snakemake

        return snakemake.__version__
    except Exception:
        return "unknown"


def create_wrapper_rulegraph(snakefile: str, profile: str, workdir: Path) -> Path:
    dotfile = workdir / ".sequana" / "rulegraph.dot"
    pngfile = workdir / ".sequana" / "rulegraph.sequana.png"
    cmd = ["snakemake", "-s", snakefile, "--profile", profile, "--rulegraph"]
    result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or f"snakemake exited with status {result.returncode}"
        raise click.ClickException(f"Could not generate rulegraph: {msg}")
    if not result.stdout.strip():
        raise click.ClickException("Could not generate rulegraph: snakemake returned an empty graph.")
    dotfile.write_text(result.stdout)
    convert_dot_to_png(str(dotfile), output=str(pngfile))
    return pngfile


def write_wrapper_summary(
    workdir: Path,
    snakefile: Path,
    profile: str,
    pipeline_name: str,
    start_dt: datetime,
    end_dt: datetime,
    returncode: int,
    rulegraph_png: Optional[Path],
) -> Path:
    summary = workdir / "summary.html"
    snakelog = workdir / ".sequana" / "snakemake.log"
    profile_config = workdir / profile / "config.yaml"
    status = "success" if returncode == 0 else "failure"
    escaped_name = html.escape(pipeline_name)
    rows = [
        ("Status", status),
        ("Exit code", str(returncode)),
        ("Snakefile", str(snakefile)),
        ("Working directory", str(workdir)),
        ("Profile", profile),
        ("Profile config", str(profile_config.resolve()) if profile_config.exists() else "not created"),
        ("Started", start_dt.isoformat()),
        ("Finished", end_dt.isoformat()),
        ("Elapsed", _format_elapsed((end_dt - start_dt).total_seconds())),
        ("Host", platform.node() or "unknown"),
        ("Platform", platform.platform()),
        ("Python", sys.version.split()[0]),
        ("Snakemake", _get_snakemake_version()),
        ("Executable", sys.executable),
    ]

    links = []
    if rulegraph_png and rulegraph_png.exists():
        links.append(
            f'<li><a href="{html.escape(os.path.relpath(rulegraph_png, workdir))}">Rulegraph PNG</a></li>'
        )
    if snakelog.exists():
        links.append(f'<li><a href="{html.escape(os.path.relpath(snakelog, workdir))}">Snakemake log</a></li>')
    if profile_config.exists():
        links.append(
            f'<li><a href="{html.escape(os.path.relpath(profile_config, workdir))}">Profile config</a></li>'
        )

    lines = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>{escaped_name} summary</title>",
        "<style>body{font-family:sans-serif;margin:2rem;line-height:1.5}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccc;padding:.4rem .6rem;text-align:left}th{background:#f5f5f5}</style>",
        "</head><body>",
        f"<h1>{escaped_name} summary</h1>",
        "<table>",
        "<tr><th>Field</th><th>Value</th></tr>",
    ]
    for key, value in rows:
        lines.append(f"<tr><td>{html.escape(key)}</td><td>{html.escape(value)}</td></tr>")
    lines.extend(["</table>"])
    if links:
        lines.append("<h2>Artifacts</h2><ul>")
        lines.extend(links)
        lines.append("</ul>")
    lines.append("</body></html>")
    summary.write_text("\n".join(lines))
    return summary


def run_wrapper(
    snakefile: str,
    workdir: str,
    wrapper_name: str,
    wrapper_profile: str,
    wrapper_jobs: int,
    wrapper_keep_going: bool,
    wrapper_slurm_memory: str,
    wrapper_slurm_queue: str,
) -> int:
    workdir_path = Path(workdir).resolve()
    workdir_path.mkdir(parents=True, exist_ok=True)
    snakefile_path = Path(snakefile).resolve()

    profile_kwargs = {
        "jobs": wrapper_jobs,
        "wrappers": os.environ.get("SEQUANA_WRAPPERS", "https://raw.githubusercontent.com/sequana/sequana-wrappers/"),
        "forceall": False,
        "keep_going": wrapper_keep_going,
        "use_apptainer": False,
        "apptainer_prefix": "",
        "apptainer_args": "",
    }
    if wrapper_profile == "slurm":
        profile_kwargs.update(
            {
                "partition": wrapper_slurm_queue,
                "qos": wrapper_slurm_queue,
                "memory": wrapper_slurm_memory,
            }
        )

    profile_dir = create_profile(workdir_path, wrapper_profile, **profile_kwargs)

    rulegraph_png = None
    try:
        rulegraph_png = create_wrapper_rulegraph(str(snakefile_path), profile_dir, workdir_path)
        click.echo(f"Created {rulegraph_png}")
    except Exception as exc:
        click.echo(f"# Warning: {exc}", err=True)

    start_dt = datetime.now().astimezone()
    returncode = run_monitor(str(snakefile_path), profile_dir, wrapper_name, "", str(workdir_path))
    end_dt = datetime.now().astimezone()
    summary = write_wrapper_summary(
        workdir_path, snakefile_path, profile_dir, wrapper_name, start_dt, end_dt, returncode, rulegraph_png
    )
    click.echo(f"Created {summary}")
    return returncode
