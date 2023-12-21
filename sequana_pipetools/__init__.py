from importlib import metadata


def get_package_version(package_name):
    try:
        version = metadata.version(package_name)
        return version
    except metadata.PackageNotFoundError:
        return f"{package_name} not found"


version = get_package_version("sequana_pipetools")

from easydev.logging_tools import Logging

logger = Logging("sequana_pipetools", "WARNING")
# To keep the inheritance/propagation of levels. Logging from easydev will do
# the formatting only.
import colorlog

logger = colorlog.getLogger(logger.name)

from .misc import url2hash
from .sequana_manager import SequanaManager  # , get_pipeline_location
from .snaketools import (
    Pipeline,
    PipelineManager,
    PipelineManagerDirectory,
    SequanaConfig,
)
