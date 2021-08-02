from sequana_pipetools.errors import *


def test_error():
    e = PipeError("fastqc")
    e.status()
