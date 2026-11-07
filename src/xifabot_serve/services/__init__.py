"""One file per service. To add an app: write services/<name>.py with `build(cfg) -> MCPServer`, add it here.

Services only give information. They must not change anything on the machine.
"""

from . import screen

SERVICES = {"screen": screen.build}
