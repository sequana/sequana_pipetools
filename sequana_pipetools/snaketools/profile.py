""" Setting up profile to setup """

try:
    import importlib.resources as resources
except ImportError:  # pragma: no cover
    # Try backported to PY<37 `importlib_resources`.
    import importlib_resources as resources


from pathlib import Path


def create_profile(workdir: Path, profile: str, **kwargs) -> str:
    """Create profile config in working directory."""
    try:
        profile_file = resources.files("sequana_pipetools.resources").joinpath(f"{profile}.yaml")
        with open(profile_file, "r") as fin:
            profile_text = fin.read()
            profile_text = profile_text.format(**kwargs)
    except AttributeError: #pragma: no cover
        # python 3.8 support for back compatibility
        with resources.path("sequana_pipetools.resources", f"{profile}.yaml") as profile_file:
            profile_text = profile_file.read_text().format(**kwargs)

    outfile = workdir / f".sequana/profile_{profile}" / "config.yaml"
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(profile_text)
    return f".sequana/profile_{profile}"
