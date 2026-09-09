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
    * - ``mistral``
      - ``MISTRAL_API_KEY``
      - default; free tier at https://console.mistral.ai/
    * - ``openai``
      - ``OPENAI_API_KEY``
      - paid account, https://platform.openai.com/
    * - ``local``
      - none
      - any OpenAI-compatible server on your machine

The ``local`` provider is the answer when you have no API key, when the
compute nodes have no internet access, or when the logs must not leave your
machine (unpublished data). It requires no credential and no network once the
model is downloaded.

Setting up a local model with Ollama
====================================

`Ollama <https://ollama.com>`_ serves an OpenAI-compatible API on
``http://localhost:11434/v1``, which is exactly the default endpoint of the
``local`` provider. Inference runs on the CPU when no GPU driver is present:
no CUDA or ROCm installation is needed.

Install it with the official script (requires root; on a machine with an
NVIDIA card it may also offer to install the CUDA driver)::

    curl -fsSL https://ollama.com/install.sh | sh

Then download a model once and diagnose::

    ollama pull llama3.2
    sequana_pipetools --diagnose --provider local

``llama3.2`` is a 3-billion-parameter model of about 2 GB, small enough for a
laptop and good enough to read a stack trace. Larger models such as
``mistral:7b`` or ``qwen2.5-coder:7b`` give a finer analysis if you have at
least 8 GB of RAM or a GPU; select one with ``--model``::

    sequana_pipetools --diagnose --provider local --model mistral:7b

Installing without root
-----------------------

The install script needs root privileges and may touch GPU driver packages.
The tarball does neither, so it is also the right choice on a cluster::

    mkdir -p ~/opt/ollama && cd ~/opt/ollama
    curl -fsSL https://ollama.com/download/ollama-linux-amd64.tgz | tar -xz
    export PATH=~/opt/ollama/bin:$PATH
    ollama serve > ~/ollama.log 2>&1 &
    ollama pull llama3.2

On a cluster, the models are several GB, so store them on a scratch partition
rather than in your home directory::

    export OLLAMA_MODELS=/path/to/scratch/$USER/ollama-models

Uninstalling is simply ``rm -rf ~/opt/ollama ~/.ollama``.

Running Ollama in a container
-----------------------------

Nothing is written outside the container storage with this variant::

    podman run -d --name ollama -p 11434:11434 -v ollama:/root/.ollama docker.io/ollama/ollama
    podman exec -it ollama ollama pull llama3.2

The same image works with apptainer::

    apptainer run docker://ollama/ollama serve

Other OpenAI-compatible servers
===============================

Any server implementing ``/v1/chat/completions`` works; point ``--base-url``
at it. This covers a vLLM or llama.cpp server, a GPU node, a router such as
OpenRouter, or an institutional gateway::

    # llama.cpp
    llama-server -m ~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf --port 8000
    sequana_pipetools --diagnose --provider local --base-url http://localhost:8000/v1

    # vLLM on a GPU node of a cluster
    sequana_pipetools --diagnose --provider local --base-url http://gpu-node042:8000/v1

    # institutional gateway (a token is usually required)
    export OPENAI_BASE_URL=https://llm.institution.fr/v1
    export OPENAI_API_KEY=<site token>
    sequana_pipetools --diagnose --provider openai

The endpoint is looked up in this order: the ``--base-url`` option, then the
``OPENAI_BASE_URL`` environment variable, then the provider default
(``http://localhost:11434/v1`` for ``local``, the official API for ``openai``).

Troubleshooting
===============

**bind: address already in use**
    A server is already listening on port 11434, most probably an Ollama
    service started at boot. Check it with ``ss -tlnp | grep 11434`` and reuse
    it instead of starting a second one. To run another instance anyway, give
    it a different port with ``OLLAMA_HOST=127.0.0.1:11435`` and pass
    ``--base-url http://localhost:11435/v1``.

**The local API call failed: Connection error**
    No server answers at the endpoint. Verify it with::

        curl http://localhost:11434/v1/models

    An empty ``"data": null`` in the answer means the server runs but no model
    has been downloaded yet: run ``ollama pull llama3.2``.

**Rate limit exceeded (HTTP 429)**
    The Mistral or OpenAI free tier is saturated. The request is retried three
    times with an exponential backoff, then the Sequana tips are printed
    without the LLM analysis. Wait a few minutes, use another key, or switch
    to ``--provider local``.

**The command is slow**
    A 3B model on a laptop CPU needs 20 to 60 seconds. A GPU, or a smaller
    model, shortens that.
