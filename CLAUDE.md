# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
poetry install --with dev              # dev setup (installs sequana-fastqc + sequana-rnaseq, needed by tests)
pytest                                 # full suite
pytest --cov=sequana_pipetools --cov-report=term-missing
pytest tests/snaketools/test_slurm.py::test_slurm -xvs   # single test
pre-commit run --all-files             # flake8 + black (line-length 120) + isort (profile black)
poetry build                           # wheel + sdist
cd doc && make html                    # Sphinx docs
```

Tests in `tests/test_manager.py` and `tests/snaketools/test_module.py` instantiate the real `fastqc`
pipeline, so they fail unless `sequana-fastqc` is installed. `graphviz` (system package) is needed for
the dot/PNG tests.

## Architecture

This is a pure-Python support library for [Sequana](https://sequana.readthedocs.io) Snakemake
pipelines. It contains no bioinformatics code and no pipelines: each pipeline
(`sequana-fastqc`, `sequana-rnaseq`, …) is a separate pip-installable package that imports this one.
Two consumers, two entry points:

1. **Pipeline `main.py` (setup time, user runs `sequana_fastqc --input-directory data`)** — builds the
   click CLI from the shared option classes, then drives `SequanaManager`.
2. **Pipeline `Snakefile` (run time)** — instantiates `PipelineManager` to resolve input files, sample
   names and wrapper versions.

### Setup path: options → SequanaManager

`options.py` exposes `init_click()`, the `include_options_from()` decorator and the `Click*Options`
classes (`ClickGeneralOptions`, `ClickSnakemakeOptions`, `ClickSlurmOptions`, `ClickInputOptions`,
`ClickTrimmingOptions`, `ClickFeatureCountsOptions`, `ClickKrakenOptions`). Each class holds a
`metadata` dict and an `options` list of click decorators; `include_options_from` applies them and
registers the group in `rich_click.OPTION_GROUPS`. **A pipeline's `main.py` must define a
module-level `NAME`** — `include_options_from` reads it out of the caller's module globals. The
non-`Click*` names (`GeneralOptions`, …) are argparse-era leftovers kept for back-compatibility.

`SequanaManager` (`sequana_manager.py`) turns parsed options into a runnable working directory:

- `setup()` creates `<workdir>/` and `<workdir>/.sequana/`.
- `teardown()` does the real work: validates the config against the pipeline schema, checks input
  files exist, writes `config.yaml` (symlinked from `.sequana/`), the `<name>.sh` launcher, the
  snakemake profile under `.sequana/profile_<profile>/`, `unlock.sh`, `pip.yml` and `info.txt`
  (versions + exact command, for reproducibility). With `--execute` it then calls `run()`.
- Apptainer/singularity images declared in the config's `apptainers:` section are downloaded
  concurrently (aiohttp), named by `url2hash`, and MD5-verified against the damona registry unless
  `--no-md5-check`.
- `Wrapper` clones/pulls `sequana-wrappers-lite` into `~/.config/sequana/wrappers`. Override with the
  `SEQUANA_WRAPPERS` env var.

`snaketools/profile.py` generates the snakemake profile and is the **snakemake v7/v8 compatibility
seam**: `_is_v8()` detects the installed version at runtime and dispatches to `_build_*_config_v7` or
`_build_*_config_v8` (v8 needs the `cluster-generic` executor plugin; SLURM resources use `mem_mb`).
Any snakemake-version-specific behaviour belongs here, not scattered in callers.

### Run path: PipelineManager → FileFactory

`snaketools/pipeline_manager.py` defines `PipelineManagerBase` (config/schema loading, `getmetadata`,
`get_shell`/`get_run` version-pinned tool invocation, `onerror`/`onsuccess` Rich panels, `teardown`
writing a cleanup Makefile), `PipelineManagerDirectory` (no input-file handling) and `PipelineManager`
(the usual case: resolves `input_directory` + `input_pattern` + `input_readtag` into `.samples`,
`.paired`, `.ff`, `.wrappers`).

Sample-name extraction lives in `snaketools/file_factory.py` and is the subtlest part of the library.
`FileFactory` cuts filenames at the first dot, then strips prefixes common to *all* files so that
`demultiplex.A.fastq.gz` yields `A`; `extra_prefixes_to_strip` and `sample_pattern`
(`"demultiplex.{sample}.fastq.gz"`, parsed with `parse`) override that heuristic. `FastQFactory`
adds read-tag splitting for paired data — the same sample name may legitimately appear twice (R1/R2)
but must otherwise be unique. Changes here break every downstream pipeline; cover them in
`tests/snaketools/test_filefactory.py`.

### Pipeline discovery

`ModuleFinder` (a `Singleton`) scans the `sequana_pipelines` namespace package with `pkgutil` to map
pipeline name → directory. `Pipeline` (`snaketools/module.py`, formerly `Module`) wraps that directory
and exposes `snakefile`, `config`, `schema_config`, `multiqc_config`, `logo`, `requirements`, `rules`.

### Config objects

`SequanaConfig` (`snaketools/sequana_config.py`) loads YAML with `ruamel.yaml` in round-trip mode so
comments survive a save; `yaml.width = 1024` prevents long-line wrapping. The parsed config is a
`_Namespace` (a `SimpleNamespace` subclass with `get`/`items`/`keys`/`values`/`in`/`[]`), so both
`cfg.section.key` and `cfg["section"]["key"]` work. `AttrDict` in `misc.py` is a backward-compatible
alias. `check_config_with_schema()` validates against the pipeline's `schema.yaml` via pykwalify;
`create_draft_schema()` backs `--config-to-schema`.

### Standalones

`scripts/main.py` is a single click command with flag-style subcommands: `--init-new-pipeline`
(cookiecutter from `sequana_pipeline_template`), `--completion`/`--overwrite` (bash + fish completion
generated by introspecting the pipeline's click command), `--slurm-diag` (`snaketools/slurm.py`,
scans `slurm*` files and `logs/`), `--stats`, `--config-to-schema`, `--dot2png`
(`snaketools/dot_parser.py`), `--url2hash`, `--diagnose`. `scripts/monitor.py` is the second entry
point (`sequana_pipetools_monitor`), backing the pipelines' `--monitor` flag.

`diagnose.py` sends trimmed snakemake/rule logs to an LLM (mistral by default via `MISTRAL_API_KEY`,
or openai via `OPENAI_API_KEY`); the provider SDKs are optional extras (`ai`, `ai-openai`), so imports
must stay lazy and the feature must degrade gracefully when they are absent.
`monitor.py` infers job state from `logs/<rule>/<sample>.log` mtimes rather than parsing snakemake
output.

## Conventions

- Keep the `Changelog` table at the bottom of `README.rst` and the `version` in `pyproject.toml` in
  sync when releasing; the changelog is the de-facto release notes.
- Public API is re-exported from `sequana_pipetools/__init__.py` and `snaketools/__init__.py`; adding
  a symbol there is what makes it part of the pipeline-facing contract.
- Options and manager behaviour are consumed by dozens of external pipeline repos — prefer adding
  optional parameters over changing existing signatures or defaults.
