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
import re
import subprocess
from pathlib import Path

import colorlog
import parse

logger = colorlog.getLogger(__name__)

__all__ = ["SlurmStats", "SlurmParsing"]


class SlurmData:
    def __init__(self, working_directory, logs_directory="logs", pattern="*/*slurm*.out"):

        # get the master slurm file
        main_slurms = list(Path(working_directory).glob("slurm-*"))

        try:
            self.master = sorted(main_slurms)[-1]
            print(f"Found slurm master {self.master}")
        except Exception as err:
            self.master = None

        log_dir = Path(working_directory) / logs_directory
        self.slurms = sorted([f for f in log_dir.glob(pattern)])


# not tested because requires sacct command
class SlurmStats(SlurmData):  # pragma: nocover
    def __init__(self, working_directory, logs_directory="logs", pattern="*/*slurm*.out"):
        super(SlurmStats, self).__init__(working_directory, logs_directory, pattern)

        results = []
        logger.info(f"Introspecting {len(self.slurms)} slurm files")
        for filename in self.slurms:

            ID = filename.name.split("-slurm-")[-1].replace(".out", "")
            task = filename.name.split("-")[0]

            # get slurm ID
            cmd = f"sacct -j {ID} --format maxRSS,AllocCPUS,Elapsed,CPUTime"
            call = subprocess.run(cmd.split(), stdout=subprocess.PIPE)
            if call.returncode == 0:
                jobinfo = self._parse_sacct_output(call.stdout.decode())
                results.append([task] + jobinfo)
            else:
                print(cmd)

        self.results = results
        self.columns = ["task", "memory_gb", "thread", "time", "cpu_time"]

    def to_csv(self, outfile):
        with open(outfile, "w") as fout:
            fout.write(",".join(self.columns) + "\n")
            for result in self.results:
                fout.write(",".join([str(x) for x in result]) + "\n")

    def _parse_sacct_output(self, output):
        """Function to parse sacct output

        The output is suppose to have 4 entries in this order:
        MaxRSS  AllocCPUS    Elapsed    CPUTime and solely used by :class:`~SlurmStats`

        """
        # Split the output into lines and remove the header
        lines = output.strip().split("\n")[2:]

        # Initialize a list to store the values of interest
        job_info = []

        # Regex to match the values
        value_regex = re.compile(r"(\S+)?\s+(\d+)\s+((?:\d+-)?\d{2}:\d{2}:\d{2})\s+((?:\d+-)?\d{2}:\d{2}:\d{2})")

        for i, line in enumerate(lines):
            match = value_regex.search(line)
            if match:
                # Extract values from regex groups
                maxrss = match.group(1) if match.group(1) else "0K"  # Handle empty MaxRSS case
                alloccpus = int(match.group(2))
                elapsed = match.group(3)
                cputime = match.group(4)

                # Only keep the second line (main job)
                if i == 1:
                    # Convert MaxRSS from KB to GB
                    maxrss_gb = self._convert_memory_to_gb(maxrss)
                    # Append parsed values to the job_info list
                    job_info = [maxrss_gb, alloccpus, elapsed, cputime]
                    break

        # Return the list of job information
        return job_info

    def _convert_memory_to_gb(self, memory_str):
        """Convert memory string to gigabytes (GB).

        Handles memory units in kilobytes (K), megabytes (M), gigabytes (G), and terabytes (T).
        """
        units = {"K": 1 / (1024**2), "M": 1 / 1024, "G": 1, "T": 1024}

        match = re.match(r"(\d+(?:\.\d+)?)([KMGT])?", memory_str)
        if match:
            value = float(match.group(1))
            unit = match.group(2) if match.group(2) else "K"  # Default to KB if no unit is specified
            return round(value * units[unit], 6)
        return 0.0  # Return 0 GB if parsing fails


class SlurmParsing(SlurmData):
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
        # "1 of 1 steps (100%) done": "Finished",
    }

    def __init__(self, working_directory, logs_directory="logs", pattern="*/*slurm*.out"):
        super(SlurmParsing, self).__init__(working_directory, logs_directory, pattern)

        # no sys exit (even zero) since it is used within snakemake
        N = len(self.slurms)
        self.errors = []
        self.percent = "undefined "

        if N == 0:  # pragma: no cover
            logger.warning(f"No {pattern} slurm files were found")
        else:  # pragma: no cover
            print(f"Found {N} slurm files to introspect in {logs_directory}. Processing.")

            # main percentage of error from master slurm
            if self.master:
                self.percent = self._get_percent()

            # whether or not we have a master file, we can scan the logs
            errors = self._get_rules_with_errors()

            if len(errors):
                for error in errors:
                    self.errors.append({"rule": error["rule"], "slurm_id": error})

    def __repr__(self):
        return self._report()

    def _report(self):
        N = len(self.errors)
        message = "#" * 33 + " DEBUG REPORT " + "#" * 33 + "\n\n"
        message += f"The analysis reached {self.percent}. A total of {N} known error(s) have been found.\n"
        if N > 0:
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
            if last_percent_parse:
                pct = last_percent_parse[-1]["percent"]
                pct = f"{pct}%"
            else:
                return "undefined status"

    def _get_rules_with_errors(self):
        """Return name and log files of rules which returned an error.,"""

        errors = """Error executing rule {rule:S} on cluster (jobid: {jobid:d}, external: Submitted batch job {slurm_id:d}, jobscript: {jobscript}). For error details see the cluster log and the log files of the involved rule(s)."""

        if self.master:
            with open(self.master, "r") as f:
                data = f.read()
                return list(parse.findall(errors, data))
        else:  # we need to introspect all slurm files
            errors = []
            for filename in self.slurms:
                with open(filename, "r") as fin:
                    data = fin.read()
                    ID = filename.name.strip(".out").split("-")[-1]
                    rule = filename.name.split("-")[0]
                    for k in self.registry.keys():
                        if k in data:
                            errors.append({"rule": rule, "slurm_id": ID})
                            break
            return errors

    def _get_error(self, filename):
        """Find known errors with a file"""
        with open(filename, "r") as f:
            data = f.read()
            for k in self.registry.keys():
                if k in data:
                    return self.registry[k]
        return "\n No registered error found"  # pragma: no cover
