"""MuckAwayAgent — waste logistics planner.

Skills:
- plan_route(origin, destination, waste_type): returns a route plan + cost
- dispatch_hauler(route_id): confirms dispatch

Triggers:
- pH<6 or ammonia>0.5 → emergency water change → dispatch hauler immediately
- normal schedule → weekly pickup

The agent receives alerts from FishKeeper via A2A and decides whether
to dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..signing import attach_signature


@dataclass
class Route:
    """A planned waste-collection route."""
    route_id: str
    origin: str
    destination: str
    waste_type: str  # "water" | "sludge" | "chemical"
    distance_km: float
    cost_gbp: float
    priority: str  # "emergency" | "scheduled" | "routine"


class MuckAwayAgent:
    """Waste logistics planner."""

    def __init__(self, name: str = "muckaway-001") -> None:
        self.name = name
        self.routes: Dict[str, Route] = {}
        self.dispatched: List[str] = []
        self.base_cost_per_km = {"water": 1.5, "sludge": 2.5, "chemical": 5.0}

    def plan_route(self, origin: str, destination: str, waste_type: str,
                    distance_km: float, priority: str = "scheduled") -> Dict[str, Any]:
        """Plan a single waste-collection route."""
        if waste_type not in self.base_cost_per_km:
            result = {
                "agent": self.name,
                "action": "plan_route",
                "status": "error",
                "reason": f"unknown waste_type '{waste_type}', must be one of {list(self.base_cost_per_km)}",
            }
            return attach_signature(result)
        route_id = f"R-{len(self.routes) + 1:04d}"
        # Priority multiplier: emergency = 2x, scheduled = 1x, routine = 0.8x
        multiplier = {"emergency": 2.0, "scheduled": 1.0, "routine": 0.8}.get(priority, 1.0)
        cost = round(distance_km * self.base_cost_per_km[waste_type] * multiplier, 2)
        route = Route(
            route_id=route_id,
            origin=origin,
            destination=destination,
            waste_type=waste_type,
            distance_km=distance_km,
            cost_gbp=cost,
            priority=priority,
        )
        self.routes[route_id] = route
        result = {
            "agent": self.name,
            "action": "plan_route",
            "route_id": route_id,
            "origin": origin,
            "destination": destination,
            "waste_type": waste_type,
            "distance_km": distance_km,
            "cost_gbp": cost,
            "priority": priority,
            "task_vector": [
                1.0 if priority == "emergency" else 0.0,
                cost / 1000.0,  # normalized
                distance_km / 100.0,
                1.0 if waste_type == "chemical" else 0.5 if waste_type == "sludge" else 0.0,
                0.0, 0.0, 0.0, 0.0,
            ],
        }
        return attach_signature(result)

    def dispatch_hauler(self, route_id: str) -> Dict[str, Any]:
        """Confirm dispatch of a planned route."""
        if route_id not in self.routes:
            result = {
                "agent": self.name,
                "action": "dispatch_hauler",
                "route_id": route_id,
                "status": "error",
                "reason": f"unknown route_id '{route_id}'",
            }
            return attach_signature(result)
        route = self.routes[route_id]
        self.dispatched.append(route_id)
        result = {
            "agent": self.name,
            "action": "dispatch_hauler",
            "route_id": route_id,
            "status": "dispatched",
            "priority": route.priority,
            "cost_gbp": route.cost_gbp,
            "eta_minutes": 60 if route.priority == "emergency" else 240,
        }
        return attach_signature(result)

    def handle_alert(self, alert_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Receive an A2A alert from another agent (FishKeeper).

        If status is 'red', automatically plan + dispatch an emergency route.
        Otherwise log and return a 'no action' response.
        """
        if alert_payload.get("status") != "red":
            result = {
                "agent": self.name,
                "action": "handle_alert",
                "status": "no_action",
                "reason": f"alert status is '{alert_payload.get('status')}', no emergency dispatch needed",
            }
            return attach_signature(result)
        # Status is red → emergency dispatch
        pond_id = alert_payload.get("pond_id", "unknown")
        route_resp = self.plan_route(
            origin=f"pond-{pond_id}",
            destination="treatment-plant-A",
            waste_type="water",
            distance_km=12.5,
            priority="emergency",
        )
        # Verify signature (defense-in-depth — even self-signed)
        from ..signing import verify_response
        if not verify_response(route_resp):
            return {"error": "self-signed route failed verification"}
        dispatch_resp = self.dispatch_hauler(route_resp["route_id"])
        return attach_signature({
            "agent": self.name,
            "action": "handle_alert",
            "alert_from": alert_payload.get("agent"),
            "pond_id": pond_id,
            "response": "emergency_dispatch",
            "route": route_resp,
            "dispatch": dispatch_resp,
        })

    def skills(self) -> Dict[str, Any]:
        """Return the public skill manifest."""
        return {
            "agent": self.name,
            "type": "waste-logistics",
            "skills": [
                {"name": "plan_route", "params": ["origin", "destination", "waste_type", "distance_km", "priority"]},
                {"name": "dispatch_hauler", "params": ["route_id"]},
                {"name": "handle_alert", "params": ["alert_payload"]},
            ],
            "pricing": {
                "plan_route": "£0.10 per call",
                "dispatch_hauler": "£1.00 per call",
                "handle_alert": "£5.00 per call (emergency)",
            },
        }


__all__ = ["MuckAwayAgent", "Route"]
