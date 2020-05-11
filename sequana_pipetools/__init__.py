import pkg_resources
try:
    version = pkg_resources.require("sequana_pipetools")[0].version
except:
    version = ">=0.2.0"


