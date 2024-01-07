#
#  This file is part of Sequana software
#
#  Copyright (c) 2016-2021 - Sequana Dev Team (https://sequana.readthedocs.io)
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  Website:       https://github.com/sequana/sequana
#  Documentation: http://sequana.readthedocs.io
#  Contributors:  https://github.com/sequana/sequana/graphs/contributors
##############################################################################
import os
import re
import sys
from pathlib import Path

import colorlog
import parse

logger = colorlog.getLogger(__name__)


class SlurmParsing:
    """Helper for sequana jobs debugging on slurm cluster.

    Assumptions:
    - Working with sequana pipelines
    - only the latests main slurm is scanned for current status
    - all slurm found in logs are then introspected

    Usage::

        from sequana_pipetools.snaketools.errors import PipeError
        p = PipeError()
        p.status()

    and more precisely::

        from sequana_pipetools.snaketools.slurm import SlurmParsing
        d = SlurmParsing(PATH)

    :param path: Path to a working directory from a sequana pipeline execution
        (Directory containing slurm_*.out files)

    """

    registry = {
        "oom_kill event in": "Out of memory. Consider increasing memory for the rule",
        "command not found": "Command not found. Check the missing tool is installed or use --use-apptainer",
        "1 of 1 steps (100%) done": "Finished",
    }

    def __init__(self, working_directory, logs_directory="logs", pattern="*/*slurm*.out"):

        # get the master slurm file
        main_slurms = list(Path(working_directory).glob("slurm-*"))
        self.master = sorted(main_slurms)[-1]

        log_dir = Path(working_directory) / logs_directory
        self.slurms = sorted([f for f in log_dir.glob(pattern)])

        N = len(self.slurms)
        if N > 0:
            print(f"Found {N} slurm files to introspect. Please wait.")
        else:  # pragma: no cover
            logger.warning(f"No {pattern} slurm files were found")
            sys.exit(0)

        # main percentage of error from master slurm
        self.percent = self._get_percent()

        # get rules with errors
        errors = self._get_rules_with_errors()
        self.errors = []

        if len(errors):
            for error in errors:
                self.errors.append({"rule": error["rule"], "slurm_id": error, "hint": error})

    def __repr__(self):
        return self._report()

    def _report(self):
        N = len(self.errors)
        message = "#" * 33 + " DEBUG REPORT " + "#" * 33 + "\n\n"
        message += f"The analysis reached {self.percent}%. A total of {N} errors has been found.\n"
        message += f"Errors are comming from rule(s): {','.join(set([e['rule'] for e in self.errors]))}\n\n"

        for e in self.errors:
            ID = e["slurm_id"]["slurm_id"]
            message += f"Errors found in {e['slurm_id']['rule']}, {ID}. "

            name = [x for x in self.slurms if str(ID) in x.name][0]
            message += self._get_error(name) + "\n"

        message += "\n" + "#" * 80

        return message

    def _get_percent(self):
        """Get at which percentage the analysis stopped"""

        step_percent = "{:d} of {:d} steps ({percent:g}%) done"

        # Get last percentage
        with open(self.master, "r") as f:
            data = f.read()
            last_percent_parse = [x for x in parse.findall(step_percent, data)]

        return last_percent_parse[-1]["percent"]

    def _get_rules_with_errors(self):
        """Return name and log files of rules which returned an error.,"""

        errors = """Error executing rule {rule:S} on cluster (jobid: {jobid:d}, external: Submitted batch job {slurm_id:d}, jobscript: {jobscript}). For error details see the cluster log and the log files of the involved rule(s)."""

        with open(self.master, "r") as f:
            data = f.read()
            return list(parse.findall(errors, data))

    def _get_error(self, filename):
        with open(filename, "r") as f:
            data = f.read()
            for k in self.registry.keys():
                if k in data:
                    return self.registry[k]
        return "\n No error found"
