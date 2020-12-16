from pathlib import Path
import parse


class DebugJob:
    """Helper for sequana jobs debugging on slurm cluster.

    Assumptions:
    - Working on slurm
    - Only a single sequana job has been launched in the path specified.

    Usage:
    DebugJob(path_to_analysis_folder)

    :param path: Path to a working directory from a sequana pipeline execution
    (Directory containing slurm_*.out files)
    """

    def __init__(self, path):
        self.path = Path(path)
        self.slurm_out = sorted([f for f in self.path.glob("slurm*.out")])

        if not self.slurm_out:
            raise IOError(f"No slurm*.out files were found in {path}")

        with open(self.slurm_out[0], "r") as f:
            self.snakemaster = f.read()

        self.percent = self._get_percent()
        (
            self.rules_with_error,
            self.error_log_files,
            self.slurm_jobids,
        ) = self._get_rules_with_errors()
        self.n_errors = len(self.rules_with_error)

    def __repr__(self):

        return self._report()

    def _report(self):

        message = "#" * 33 + " DEBUG REPORT " + "#" * 33 + "\n\n"
        message += f"The analysis reached {self.percent}%. A total of {self.n_errors} errors has been found.\n\n"

        if self.n_errors:
            message += f"Rules with errors are: {', '.join(self.rules_with_error)}\n\n"
            message += "Following are the corresponding logs:\n\n"

            self.error_log = ""
            for log in self.error_log_files:
                with open(log, "r") as l:
                    self.error_log += f"File: {log}:\n"
                    self.error_log += "-" * 80 + "\n\n"
                    self.error_log += l.read()
                    self.error_log += "=" * 80 + "\n\n"

            message += f"{self.error_log}\n"

        message += "\n" + "#" * 80
        return message

    def _get_percent(self):
        """Get at which percentage the analysis stopped"""

        step_percent = "{:d} of {:d} steps ({percent:g}%) done"

        # Get last percentage
        last_percent_parse = [x for x in parse.findall(step_percent, self.snakemaster)]
        return last_percent_parse[-1]["percent"]

    def _get_rules_with_errors(self):
        """Return name and log files of rules which returned an error.,"""

        errors = """Error in rule {rule:S}:
    jobid: {jobid:d}
    output: {output}
    log: {log:S} (check log file(s) for error message)
    cluster_jobid: Submitted batch job {slurm_jobid:d}"""

        rules_with_error = [e["rule"] for e in parse.findall(errors, self.snakemaster)]
        error_log_files = [
            self.path / e["log"] for e in parse.findall(errors, self.snakemaster)
        ]
        slurm_jobids = [
            e["slurm_jobid"] for e in parse.findall(errors, self.snakemaster)
        ]

        return (rules_with_error, error_log_files, slurm_jobids)
