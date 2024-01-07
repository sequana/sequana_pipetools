from sequana_pipetools.snaketools.errors import *

from . import test_dir

sharedir = Path(f"{test_dir}/data")


def test_error():
    e = PipeError("fastqc")
    e.status(sharedir)
