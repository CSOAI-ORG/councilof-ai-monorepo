"""J-Space: chess-board package."""
from .move_arithmetic import (
    Axis, Move, ErrorVector,
    ties_merge, dare_dropout, subtract_error,
    JSpaceRouter,
)

__version__ = "0.1.0"
__all__ = [
    "Axis", "Move", "ErrorVector",
    "ties_merge", "dare_dropout", "subtract_error",
    "JSpaceRouter",
]