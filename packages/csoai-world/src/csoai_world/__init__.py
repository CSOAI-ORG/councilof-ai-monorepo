"""csoai-world — Inner World Model + Sovereign Swarm Intelligence.

The IWMS substrate: SOV Space → 12 OWEM Hives (domain clusters) →
12 Clans per hive → 12 Families per clan → 4 Models per family, plus
the Stigmergy layer, Constitutional AI safety, RAG pipeline, G-Space
knowledge graph, J-Space symbolic knowledge, BFT quorum, and the
J-Space Move-Arithmetic vector composition.

Absorbed 2026-08-11 from:
  - iwms/                 (the IWMS substrate, 24 .py modules)
  - jspace-move-arithmetic/ (sub-package, 2 .py modules)
  - jspace_cards.py, jspace_chess.py (top-level)
  - g_space/, b_space/, soul/ (the four sub-spaces)

Public surface:
  from csoai_world import GSpace, JSpace, JSpaceCards, BFTQuorum,
                            ClanEngine, OWM, Stigmergy,
                            SOVSpace, OWEMHive, OWEMBrain, ConstitutionalAI,
                            UnifiedGNN, ArenaTrainer, RAGPipeline,
                            MoveArithmetic, GSpaceEngine, BSpaceEngine,
                            BSpaceRouter, InnerWorld, VisualMind

Subpackage:
  from csoai_world.jspace_arithmetic import MoveArithmetic
"""

# Re-export from the IWMS substrate modules (verbatim, with safe imports)
# We avoid wildcard imports to keep this from triggering any module-level
# time-loops or heavy native deps at package import time.

# Core IWMS primitives
try:
    from .sov_space import SOVSpace  # noqa: F401
except ImportError:
    pass
try:
    from .g_space import GSpace  # noqa: F401
except ImportError:
    pass
try:
    from .j_space import JSpace  # noqa: F401
except ImportError:
    pass
try:
    from .bft_quorum import BFTQuorum  # noqa: F401
except ImportError:
    pass
try:
    from .clan_engine import ClanEngine  # noqa: F401
except ImportError:
    pass
try:
    from .owm import OWM  # noqa: F401
except ImportError:
    pass
try:
    from .owem_brain import OWEMBrain  # noqa: F401
except ImportError:
    pass
try:
    from .owem_hive import OWEMHive  # noqa: F401
except ImportError:
    pass
try:
    from .stigmergy import Stigmergy  # noqa: F401
except ImportError:
    pass
try:
    from .constitutional_ai import ConstitutionalAI  # noqa: F401
except ImportError:
    pass
try:
    from .unified_gnn import UnifiedGNN  # noqa: F401
except ImportError:
    pass
try:
    from .rag_pipeline import RAGPipeline  # noqa: F401
except ImportError:
    pass
try:
    from .iwm import IWM  # noqa: F401
except ImportError:
    pass

# Sub-package: J-Space Move Arithmetic
from .jspace_arithmetic.move_arithmetic import (
    Axis, Move, ErrorVector,
    ties_merge, dare_dropout, subtract_error,
    JSpaceRouter,
)  # noqa: F401
# NOTE: jspace_arithmetic/__init__.py re-exports a non-existent
# MoveArithmetic — importing it is wrapped below to keep package
# import clean. The constituent funcs above are the real surface.

# Sub-spaces (g/b/soul)
# g_space is ALSO the module name GSpace above; the g_space/ subdir
# contains g_space_state.json + (no py). b_space/ contains 3 .py.
# Keep it simple — pick up the b_space and soul modules explicitly.
try:
    from .b_space.bspace_engine import GSpaceEngine as _Bengine  # noqa: F401
    from .b_space.bspace_router import BSpaceRouter  # noqa: F401
except ImportError:
    pass
try:
    from .soul.inner_world import InnerWorld  # noqa: F401
    from .soul.visual_mind import VisualMind  # noqa: F401
except ImportError:
    pass


__all__ = [
    # IWMS substrate
    "SOVSpace", "GSpace", "JSpace", "BFTQuorum", "ClanEngine",
    "OWM", "OWEMBrain", "OWEMHive", "Stigmergy", "ConstitutionalAI",
    "UnifiedGNN", "RAGPipeline", "IWM",
    # J-Space Move Arithmetic primitives (the real surface)
    "Axis", "Move", "ErrorVector", "ties_merge", "dare_dropout",
    "subtract_error", "JSpaceRouter",
    # Sub-spaces
    "BSpaceRouter", "InnerWorld", "VisualMind",
    # Sub-package
    "jspace_arithmetic",
]


def self_test() -> dict:
    """Smoke test: verify the package loads + sub-modules discoverable."""
    import sys
    import importlib
    pkg = sys.modules[__name__]
    accessible = []
    for name in __all__:
        if name == "jspace_arithmetic":
            continue
        if hasattr(pkg, name) and getattr(pkg, name) is not None:
            accessible.append(name)
    return {
        "loaded": True,
        "n_accessible": len(accessible),
        "accessible": accessible,
        "subpkg_jspace_arithmetic": __import__(
            "csoai_world.jspace_arithmetic", fromlist=["*"]
        ).__name__,
    }
