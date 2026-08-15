"""
sovos/quantum/photonic.py
Photonic Fabric — CPO (Co-Packaged Optics) management.
Simulates and eventually controls the physical photonic layer.
"""
from __future__ import annotations
from typing import Any, Dict, List
from dataclasses import dataclass


@dataclass
class PhotonicChannel:
    """A single photonic channel in the CPO fabric."""
    channel_id: str
    wavelength_nm: float = 1550.0  # Telecom C-band
    bandwidth_ghz: float = 50.0
    power_dbm: float = 0.0
    mode: str = "classical"  # "classical" | "quantum" | "hybrid"
    active: bool = True

    def to_cpo_link_spec(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "wavelength_nm": self.wavelength_nm,
            "bandwidth_ghz": self.bandwidth_ghz,
            "power_dbm": self.power_dbm,
            "mode": self.mode,
            "active": self.active,
        }


class CPOFabric:
    """
    Co-Packaged Optics Fabric Manager.
    Manages photonic channels between compute nodes.
    Power: ~9W per 1.6T link (vs 30W pluggable).
    """
    def __init__(self) -> None:
        self.channels: Dict[str, PhotonicChannel] = {}
        self.total_power_budget_w = 1000.0  # 1kW rack budget

    def add_channel(self, ch: PhotonicChannel) -> None:
        self.channels[ch.channel_id] = ch

    def power_consumption(self) -> float:
        """Total CPO power in watts."""
        # 9W per active channel at 1.6T
        active = sum(1 for c in self.channels.values() if c.active)
        return active * 9.0

    def savings_vs_pluggable(self) -> Dict[str, float]:
        """Compare CPO vs traditional pluggable optics."""
        active = sum(1 for c in self.channels.values() if c.active)
        cpo_power = active * 9.0
        pluggable_power = active * 30.0
        return {
            "cpo_power_w": cpo_power,
            "pluggable_power_w": pluggable_power,
            "savings_w": pluggable_power - cpo_power,
            "savings_percent": ((pluggable_power - cpo_power) / pluggable_power) * 100,
        }

    def list_channels(self, mode: str = None) -> List[PhotonicChannel]:
        if mode:
            return [c for c in self.channels.values() if c.mode == mode]
        return list(self.channels.values())

    def fabric_map(self) -> Dict[str, Any]:
        return {
            "channels": {k: v.to_cpo_link_spec() for k, v in self.channels.items()},
            "power": self.power_consumption(),
            "savings": self.savings_vs_pluggable(),
        }
