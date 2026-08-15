"""csoai_x402_gate — The public HTTP 402 paywall server.

This is the SOVOS x402 paywall implementation: the *intentional* 402.
When an unauthenticated caller hits a paid endpoint, the server returns
a real HTTP 402 Payment Required response with the canonical headers
that x402-aware agents/clients understand:

    HTTP/1.1 402 Payment Required
    Content-Type: application/json
    WWW-Authenticate: x402 realm="sovos", price="0.05", currency="USDC",
                       pay_to="0x...:base", asset="USDC"
    X-Payment-Required: sovos-v1
    X-SOVOS-Pricing: https://meok.ai/pricing

    {
      "error": "payment_required",
      "reason": "MEOK_PAYG_KEY not set",
      "upgrade_url": "https://buy.stripe.com/5kQ6oJ0xS3ce8sl7ew8k91j",
      "payg_enabled": false,
      "pricing": "https://meok.ai/pricing",
      "sovos_chain_id": "<sha256>"
    }

Why a dedicated package?
------------------------
1. **Decoupling** — the x402 decision is a *protocol* concern, not a
   per-tool concern. Centralizing it lets every MCP server in the fleet
   opt in with one decorator.

2. **Honest 402s** — the most common bug in MCP monetization today is
   returning an *accidental* 402 (Vercel billing, x402 paywall, Stripe
   unpaid tier all conflated). This package makes the 402 **intentional**
   by always including the canonical headers + a structured body.

3. **Audit trail** — every 402 emits a SIGIL-style chain_id so the OWEM
   hive can later analyze the rejection pattern.

Public API:
    from csoai_x402_gate import paywall, x402_decorator

    # Use the decorator to wrap any function that needs a paywall:
    @x402_decorator(price_usdc="0.05")
    def my_paid_tool(...): ...

    # Or check directly:
    if paywall.should_require_payment(request):
        return paywall.payment_required_response()
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants — the canonical CSOAI payment surface
# ---------------------------------------------------------------------------
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/5kQ6oJ0xS3ce8sl7ew8k91j"
MEOK_PAYG_PRICING = "https://meok.ai/pricing"
MEOK_PAYG_PRICE_USDC = "0.05"  # ~£0.05 per call
MEOK_PAYG_PAY_TO = "0x0000000000000000000000000000000000000000:base"  # placeholder
MEOK_PAYG_ASSET = "USDC"
SOVOS_X402_VERSION = "sovos-v1"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class PaywallConfig:
    """Configuration for one paywalled endpoint."""
    price_usdc: str = MEOK_PAYG_PRICE_USDC
    pay_to: str = MEOK_PAYG_PAY_TO
    asset: str = MEOK_PAYG_ASSET
    realm: str = "sovos"
    upgrade_url: str = MEOK_STRIPE_UPGRADE
    pricing_url: str = MEOK_PAYG_PRICING
    enabled: bool = True  # global kill-switch

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PaywallVerdict:
    """The result of a paywall check."""
    allowed: bool
    reason: str
    chain_id: str
    payg_key_present: bool
    stripe_active: bool
    config: PaywallConfig
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["config"] = self.config.to_dict()
        return d

    def to_http_response(self) -> Dict[str, Any]:
        """Render as a canonical HTTP 402 response (status, headers, body)."""
        if self.allowed:
            return {
                "status": 200,
                "headers": {"X-SOVOS-Paywall": "ok", "X-SOVOS-Chain-Id": self.chain_id},
                "body": {"ok": True, "chain_id": self.chain_id},
            }
        # The intentional 402
        www_auth = (
            f'x402 realm="{self.config.realm}", '
            f'price="{self.config.price_usdc}", '
            f'currency="{self.config.asset}", '
            f'pay_to="{self.config.pay_to}", '
            f'asset="{self.config.asset}"'
        )
        body = {
            "error": "payment_required",
            "reason": self.reason,
            "upgrade_url": self.config.upgrade_url,
            "payg_enabled": self.payg_key_present,
            "pricing": self.config.pricing_url,
            "sovos_chain_id": self.chain_id,
            "version": SOVOS_X402_VERSION,
        }
        return {
            "status": 402,
            "headers": {
                "Content-Type": "application/json",
                "WWW-Authenticate": www_auth,
                "X-Payment-Required": SOVOS_X402_VERSION,
                "X-SOVOS-Pricing": self.config.pricing_url,
                "X-SOVOS-Chain-Id": self.chain_id,
            },
            "body": body,
        }


# ---------------------------------------------------------------------------
# Paywall — the singleton check
# ---------------------------------------------------------------------------
class Paywall:
    """The x402 paywall. Single source of truth for the public 402 decision."""

    def __init__(self, config: Optional[PaywallConfig] = None):
        self.config = config or PaywallConfig()

    def check(self, request_meta: Optional[Dict[str, Any]] = None,
              payg_key: Optional[str] = None,
              stripe_active: Optional[bool] = None) -> PaywallVerdict:
        """Decide whether the caller can proceed.

        Args:
            request_meta: optional dict with caller info (headers, ip, etc.)
                          — included in the chain_id for audit trail
            payg_key:    the caller's MEOK_PAYG_KEY (env or header)
            stripe_active: True if the caller's Stripe tier is active

        Returns:
            PaywallVerdict with allowed=True iff the caller is paid.
        """
        # Determine payg_key presence
        env_payg = os.environ.get("MEOK_PAYG_KEY", "")
        payg_present = bool(payg_key or env_payg)
        # Determine Stripe active
        if stripe_active is None:
            stripe_active = payg_present  # conservative default
        # Decide
        allowed = payg_present or stripe_active
        reason = "OK" if allowed else "MEOK_PAYG_KEY not set; upgrade or set PAYG key"
        # Build chain_id from inputs (audit trail)
        body = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "payg_present": payg_present,
            "stripe_active": stripe_active,
            "request_meta": request_meta or {},
        }, sort_keys=True, default=str).encode()
        chain_id = hashlib.sha256(body).hexdigest()[:24]
        return PaywallVerdict(
            allowed=allowed, reason=reason, chain_id=chain_id,
            payg_key_present=payg_present, stripe_active=stripe_active,
            config=self.config,
        )

    def require_payment(self, request_meta: Optional[Dict[str, Any]] = None,
                        payg_key: Optional[str] = None) -> Dict[str, Any]:
        """Convenience: return the canonical 402 response if payment required."""
        verdict = self.check(request_meta=request_meta, payg_key=payg_key)
        return verdict.to_http_response()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_paywall: Optional[Paywall] = None


def paywall() -> Paywall:
    """Return the module-level Paywall singleton."""
    global _paywall
    if _paywall is None:
        _paywall = Paywall()
    return _paywall


# ---------------------------------------------------------------------------
# Decorator — the 1-line opt-in for any paid tool
# ---------------------------------------------------------------------------
def x402_decorator(price_usdc: str = MEOK_PAYG_PRICE_USDC):
    """Decorator that wraps a function with the x402 paywall check.

    Usage:
        @x402_decorator(price_usdc="0.10")
        def my_paid_tool(x: int) -> dict:
            return {"result": x * 2}

    The wrapped function returns a dict like:
        {"status": 200, "headers": {...}, "body": {"ok": True, "result": 4}}
        OR
        {"status": 402, "headers": {...}, "body": {"error": "payment_required", ...}}

    This way the caller (an MCP server or a FastAPI handler) can pass
    the result straight through to the HTTP response.
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        config = PaywallConfig(price_usdc=price_usdc)
        wall = Paywall(config)

        def wrapper(*args: Any, payg_key: Optional[str] = None,
                    request_meta: Optional[Dict[str, Any]] = None,
                    **kwargs: Any) -> Dict[str, Any]:
            verdict = wall.check(request_meta=request_meta, payg_key=payg_key)
            resp = verdict.to_http_response()
            if not verdict.allowed:
                return resp
            try:
                result = fn(*args, **kwargs)
                resp["body"] = {"ok": True, "result": result,
                                "sovos_chain_id": verdict.chain_id}
                return resp
            except Exception as e:
                return {
                    "status": 500,
                    "headers": {"X-SOVOS-Chain-Id": verdict.chain_id},
                    "body": {"error": "internal_error", "detail": str(e),
                             "sovos_chain_id": verdict.chain_id},
                }
        wrapper.__wrapped__ = fn  # for introspection
        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def self_test() -> Dict[str, Any]:
    """Smoke test: check that the canonical 402 decision works."""
    p = Paywall()
    # No payg, no stripe → 402
    denied = p.check()
    denied_resp = denied.to_http_response()
    # With payg → 200
    allowed = p.check(payg_key="sk_test_abc")
    allowed_resp = allowed.to_http_response()

    return {
        "denied_status": denied_resp["status"],
        "denied_www_auth_present": "WWW-Authenticate" in denied_resp["headers"],
        "denied_x_payment_present": "X-Payment-Required" in denied_resp["headers"],
        "denied_body_error": denied_resp["body"]["error"],
        "allowed_status": allowed_resp["status"],
        "denied_chain_id_len": len(denied.chain_id),
        "allowed_chain_id_len": len(allowed.chain_id),
    }


# CLI smoke
if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
