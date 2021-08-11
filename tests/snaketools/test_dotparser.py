import os

from sequana_pipetools.snaketools import DOTParser

from .. import test_dir


def test_dot_parser():
    s = DOTParser(os.path.join(test_dir, "data", "test_dag.dot"))
    s.add_urls(mapper={"bwa_fix": "test.html"})
    try:
        os.remove("test_dag.ann.dot")
    except FileNotFoundError:
        pass

    s.mode = "v1"
    s.add_urls(mapper={"bwa_fix": "test.html"})
    try:
        os.remove("test_dag.ann.dot")
    except FileNotFoundError:
        pass
