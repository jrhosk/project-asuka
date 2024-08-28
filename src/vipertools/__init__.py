import os
from importlib.metadata import version

__version__ = version("vipertools")

from . import graph
from . import mstools
from . import security

# Set parameter checking system directory.
if os.path.exists(os.path.dirname(__file__) + "/config/"):
    os.environ["TOOLS_CONFIG_PATH"] = os.path.dirname(__file__) + "/config/"