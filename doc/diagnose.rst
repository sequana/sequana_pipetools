Diagnosing pipeline errors with an LLM
######################################

When a Sequana pipeline fails, ``sequana_pipetools --diagnose`` collects the
snakemake log and the logs of the failed rules, asks a Large Language Model to
explain the failure in plain language, and appends a list of deterministic
Sequana tips (how to re-run, how to unlock the directory, which tool is
missing, and so on)::

    cd /path/to/pipeline/working/directory
    sequana_pipetools --diagnose

The tips are always printed, even when no model can be reached, so the command
is never a dead end.

Working without any LLM
=======================

Part of the analysis needs no model at all. The logs are scanned for a
catalogue of known Sequana and snakemake failures, and each match produces a
concrete fix:

.. list-table::
    :header-rows: 1
    :widths: 45 55

    * - Detected in the logs
      - Tip
    * - ``<tool>: command not found``, exit code 127
      - ``damona install <tool>``
    * - ``MissingInputException``
      - check ``input_directory``, ``input_pattern`` and the read tag
    * - ``IncompleteFilesException``
      - re-run with ``--rerun-incomplete``
    * - ``Missing files after N seconds``
      - inspect ``logs/<rule>/<sample>.log``, raise ``--latency-wait``
    * - ``oom-kill``, ``OUT_OF_MEMORY``, exit code 137
      - raise the memory in the SLURM profile or ``--resources mem_mb=``
    * - ``DUE TO TIME LIMIT``
      - raise the walltime in the SLURM profile
    * - ``No space left on device``, ``Disk quota exceeded``
      - free space or move to a scratch partition
    * - ``Permission denied``
      - check permissions of the working directory and inputs
    * - ``pykwalify``, ``SchemaError``
      - fix the reported key in config.yaml
    * - singularity/apptainer failure, md5 mismatch
      - re-download, or share images with ``--apptainer-prefix``
    * - ``Directory cannot be locked``
      - ``sh unlock.sh``

These tips are printed in three situations: appended below the LLM answer,
alone when no provider can be reached (missing key, missing package, endpoint
down, rate limit), and in the panel a pipeline prints by itself when it fails,
before you run any command.

Choosing a provider
===================

Three providers are available through the ``--provider`` option.

.. list-table::
    :header-rows: 1
    :widths: 15 25 60

    * - Provider
      - Credential
      - Comment
    * - ``claude-code``
      - none (Claude Code login)
      - default; runs the ``claude`` CLI in headless mode and uses your Claude subscription
    * - ``claude``
      - ``ANTHROPIC_API_KEY``
      - Anthropic API, https://console.anthropic.com/ (``pip install sequana_pipetools[ai-claude]``)
    * - ``openai``
      - ``OPENAI_API_KEY``
      - paid account, https://platform.openai.com/ (``pip install sequana_pipetools[ai-openai]``)

OpenAI-compatible gateways
==========================

The ``openai`` provider also talks to any server implementing
``/v1/chat/completions`` (a router such as OpenRouter, or an institutional
gateway). Point it there with ``--base-url`` or ``OPENAI_BASE_URL``::

    export OPENAI_BASE_URL=https://llm.institution.fr/v1
    export OPENAI_API_KEY=<site token>
    sequana_pipetools --diagnose --provider openai

The ``--base-url`` option takes precedence over ``OPENAI_BASE_URL``. Without
either, the official OpenAI API is used.

Troubleshooting
===============

**Rate limit exceeded (HTTP 429)**
    The provider quota is saturated. The request is retried three
    times with an exponential backoff, then the Sequana tips are printed
    without the LLM analysis. Wait a few minutes, use another key, or switch
    to another ``--provider``.
