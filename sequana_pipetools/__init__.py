import pkg_resources

try:
    version = pkg_resources.require("sequana_pipetools")[0].version
except pkg_resources.DistributionNotFound:  # pragma: no cover
    version = ">=0.2.0"


from easydev.logging_tools import Logging

logger = Logging("sequana_pipetools", "WARNING")
# To keep the inheritance/propagation of levels. Logging from easydev will do
# the formatting only.
import colorlog

logger = colorlog.getLogger(logger.name)

from .sequana_manager import SequanaManager, get_pipeline_location
from .snaketools import Module, PipelineManager, PipelineManagerDirectory, SequanaConfig
from .misc import url2hash
