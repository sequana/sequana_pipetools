from pathlib import Path
import parse


class DebugJob:
    """Helper for sequana jobs debugging on slurm cluster.

    Assumptions:
    - Working on slurm
    - Only a single sequana job has been launched in the path specified.

    :param path: Path to a working directory from a sequana pipeline execution
    (Directory containing slurm_*.out files)
    """

    def __init__(self, path):
        self.path = Path(path)
        self.slurm_out = sorted([f for f in self.path.glob("slurm*.out")])

        self._parse_snakemaster()

    def __repr__(self):

        message = "#" * 33 + " DEBUG REPORT " + "#" * 33 + "\n\n"
        message += f"A total of {self.n_errors} errors have been found.\n"
        message += f"Rules with errors are: {', '.join(self.rules_with_error)}\n\n"
        message += "Following are the corresponding logs:\n\n"
        message += f"{self.error_log}"

        return message

    def _parse_snakemaster(self):
        """Parse the main snakemake output file"""

        step_percent = "{:d} of {:d} steps ({percent:g}%) done"
        errors = """Error in rule {rule:S}:
    jobid: {jobid:d}
    output: {output:S}
    log: {log:S} (check log file(s) for error message)
    """

        with open(self.slurm_out[0], "r") as snakemaster:

            f = snakemaster.read()
            # Get last percentage
            last_percent_parse = [x for x in parse.findall(step_percent, f)][-1]

            self.percent = last_percent_parse["percent"]

            self.rules_with_error = [e["rule"] for e in parse.findall(errors, f)]
            self.error_log_files = [
                self.path / e["log"] for e in parse.findall(errors, f)
            ]

            self.error_log = ""
            for log in self.error_log_files:
                with open(log, "r") as l:
                    self.error_log += f"File: {log}:\n"
                    self.error_log += "-" * 80 + "\n\n"
                    self.error_log += l.read()
                    self.error_log += "=" * 80 + "\n\n"

            self.n_errors = len(self.rules_with_error)
