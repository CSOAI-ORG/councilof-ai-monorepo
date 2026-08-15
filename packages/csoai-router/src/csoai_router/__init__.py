"""csoai-router — selective re-exports of the absorbed connectivity surface.

The absorbed scripts come in two shapes:

  1. **Library modules** (importable, no side effects):
     sov4_router, sov_orchestrator, master_hives, owem_cluster,
     router_control, fleet_dashboard, fleet_power.

  2. **Standalone time-loops** (run as scripts only; imported as `*` would
     trigger them):  fleet_monitor, sov_swarm.

This `__init__.py` selectively re-exports shape 1. Shape 2 stays
present in the package filesystem but is invoked explicitly:

    python3 SOVOS/packages/csoai-router/src/csoai_router/fleet_monitor.py
"""
from .sov4_router import *           # noqa: F401,F403
from .sov_orchestrator import *      # noqa: F401,F403
from .master_hives import *         # noqa: F401,F403
from .owem_cluster import *         # noqa: F401,F403
from .router_control import *       # noqa: F401,F403
from .fleet_dashboard import *      # noqa: F401,F403
from .fleet_power import *          # noqa: F401,F403

# NOTE: sov_swarm and fleet_monitor are deliberately NOT imported here.
# They have module-level time-loops and must be invoked as scripts.
# Access them via:  from csoai_router.sov_swarm import ...   (if you want
# symbols without triggering the loop, refactor inside the script).

__all__ = [
    "sov4_router", "sov_orchestrator",
    "master_hives", "owem_cluster", "router_control",
    "fleet_dashboard", "fleet_power",
]
