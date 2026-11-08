"""One file per service, each with `build(cfg) -> MCPServer`, and one line here.

A service answers requests about its own app or area: information, or work it does itself (later, for example, a
game service). Services never run arbitrary commands on the PC.
"""

from . import screen

SERVICES = {"screen": screen.build}
