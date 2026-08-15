"""csoai-mind: one mind, one monorepo, water → milk → honey → action.

SovosMind is the unified orchestrator that ties together:
- StateBus (state.py) — one memory fabric
- Layer0Fabric (layer0.py) — CPO + MCP + A2A substrate
- WaterIngestion (water.py) — raw data ingestion
- MilkProcessor (milk.py) — task-vector hive transforms
- HoneyDistiller (honey.py) — semantic routing + decisions
"""
from .state import StateBus, StateVector
from .layer0 import Layer0Fabric, CPOLink, MCPTool, A2AAgent
from .water import WaterIngestion, IngestionSource
from .milk import MilkProcessor, HiveConfig, HiveMode, HiveAxis
from .honey import HoneyDistiller, Decision
from .mind import SovosMind, ThinkResult

__version__ = "0.1.0"
__all__ = [
    "StateBus", "StateVector",
    "Layer0Fabric", "CPOLink", "MCPTool", "A2AAgent",
    "WaterIngestion", "IngestionSource",
    "MilkProcessor", "HiveConfig", "HiveMode", "HiveAxis",
    "HoneyDistiller", "Decision",
    "SovosMind", "ThinkResult",
]