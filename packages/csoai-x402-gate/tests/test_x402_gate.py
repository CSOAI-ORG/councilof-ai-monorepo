"""Tests for csoai_x402_gate — the intentional HTTP 402 paywall."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import os

from csoai_x402_gate import (
    MEOK_PAYG_ASSET,
    MEOK_PAYG_PRICE_USDC,
    MEOK_STRIPE_UPGRADE,
    SOVOS_X402_VERSION,
    Paywall,
    PaywallConfig,
    paywall,
    self_test,
    x402_decorator,
)


def test_x402_01_paywall_denied_no_key():
    """No payg_key, no stripe → 402 with canonical headers."""
    # Make sure no env var pollutes the test
    os.environ.pop("MEOK_PAYG_KEY", None)
    p = Paywall()
    v = p.check()
    resp = v.to_http_response()
    assert resp["status"] == 402
    assert "WWW-Authenticate" in resp["headers"]
    assert "x402" in resp["headers"]["WWW-Authenticate"]
    assert f'price="{MEOK_PAYG_PRICE_USDC}"' in resp["headers"]["WWW-Authenticate"]
    assert resp["headers"]["X-Payment-Required"] == SOVOS_X402_VERSION
    assert resp["body"]["error"] == "payment_required"
    assert resp["body"]["upgrade_url"] == MEOK_STRIPE_UPGRADE
    print(f"  ✅ denied → 402 with x402 canonical headers")


def test_x402_02_paywall_allowed_with_payg():
    """payg_key="..." → 200."""
    p = Paywall()
    v = p.check(payg_key="sk_test_abc")
    resp = v.to_http_response()
    assert resp["status"] == 200
    assert "X-SOVOS-Paywall" in resp["headers"]
    assert resp["headers"]["X-SOVOS-Paywall"] == "ok"
    print(f"  ✅ allowed → 200 with X-SOVOS-Paywall: ok")


def test_x402_03_paywall_allowed_with_stripe():
    """stripe_active=True → 200 even without payg_key."""
    p = Paywall()
    v = p.check(stripe_active=True)
    assert v.allowed
    assert v.stripe_active
    print(f"  ✅ stripe tier active → allowed")


def test_x402_04_chain_id_is_audit_hash():
    """chain_id is a 24-char sha256 hex of inputs."""
    p = Paywall()
    v = p.check(payg_key="abc")
    assert len(v.chain_id) == 24
    assert all(c in "0123456789abcdef" for c in v.chain_id)
    # Different inputs → different ids
    v2 = p.check(payg_key="xyz")
    assert v.chain_id != v2.chain_id
    print(f"  ✅ chain_id is 24-char sha256, deterministic per input")


def test_x402_05_env_var_picks_up_payg_key():
    """If MEOK_PAYG_KEY is set in env, paywall is open."""
    p = Paywall()
    os.environ["MEOK_PAYG_KEY"] = "sk_live_test"
    try:
        v = p.check()
        assert v.allowed
        assert v.payg_key_present
        print(f"  ✅ env var MEOK_PAYG_KEY → allowed")
    finally:
        del os.environ["MEOK_PAYG_KEY"]


def test_x402_06_decorator_with_paid_key():
    """The decorator returns 200 + result when payg_key provided."""
    @x402_decorator(price_usdc="0.10")
    def double(x: int) -> int:
        """Returns x * 2."""
        return x * 2

    r = double(5, payg_key="sk_test_abc")
    assert r["status"] == 200
    assert r["body"]["ok"] is True
    assert r["body"]["result"] == 10
    print(f"  ✅ decorator: payg_key → 200, result={r['body']['result']}")


def test_x402_07_decorator_without_paid_key():
    """The decorator returns 402 when no payg_key."""
    @x402_decorator(price_usdc="0.10")
    def double(x: int) -> int:
        """Returns x * 2."""
        return x * 2

    r = double(5)
    assert r["status"] == 402
    assert "WWW-Authenticate" in r["headers"]
    assert r["body"]["error"] == "payment_required"
    print(f"  ✅ decorator: no key → 402 with WWW-Authenticate")


def test_x402_08_decorator_handles_exception():
    """The decorator catches exceptions and returns 500 + chain_id."""
    @x402_decorator(price_usdc="0.05")
    def boom(x: int) -> int:
        """Raises."""
        raise ValueError("nope")

    r = boom(1, payg_key="sk_test_abc")
    assert r["status"] == 500
    assert "sovos_chain_id" in r["body"]
    assert r["body"]["error"] == "internal_error"
    print(f"  ✅ decorator: exception → 500 with chain_id preserved")


def test_x402_09_singleton_paywall():
    """paywall() returns the same Paywall singleton across calls."""
    a = paywall()
    b = paywall()
    assert a is b
    print(f"  ✅ paywall() is a singleton")


def test_x402_10_custom_config():
    """Custom PaywallConfig overrides price + pay_to."""
    cfg = PaywallConfig(
        price_usdc="1.00",
        pay_to="0xABC:ethereum",
        asset="USDC",
        realm="my-sovos",
    )
    p = Paywall(cfg)
    v = p.check()
    resp = v.to_http_response()
    assert 'price="1.00"' in resp["headers"]["WWW-Authenticate"]
    assert 'pay_to="0xABC:ethereum"' in resp["headers"]["WWW-Authenticate"]
    print(f"  ✅ custom config: price=1.00 USDC, pay_to=0xABC:ethereum")


def test_x402_11_request_meta_in_chain_id():
    """request_meta flows into the chain_id for audit trail."""
    p = Paywall()
    v1 = p.check(payg_key="abc", request_meta={"ip": "1.2.3.4"})
    v2 = p.check(payg_key="abc", request_meta={"ip": "5.6.7.8"})
    # Both allowed but chain_ids differ (request_meta included)
    assert v1.chain_id != v2.chain_id
    print(f"  ✅ request_meta → different chain_ids (audit trail)")


def test_x402_12_self_test():
    """self_test returns a complete picture."""
    info = self_test()
    assert info["denied_status"] == 402
    assert info["allowed_status"] == 200
    assert info["denied_www_auth_present"] is True
    assert info["denied_x_payment_present"] is True
    print(f"  ✅ self_test: {info}")


if __name__ == "__main__":
    tests = [
        test_x402_01_paywall_denied_no_key,
        test_x402_02_paywall_allowed_with_payg,
        test_x402_03_paywall_allowed_with_stripe,
        test_x402_04_chain_id_is_audit_hash,
        test_x402_05_env_var_picks_up_payg_key,
        test_x402_06_decorator_with_paid_key,
        test_x402_07_decorator_without_paid_key,
        test_x402_08_decorator_handles_exception,
        test_x402_09_singleton_paywall,
        test_x402_10_custom_config,
        test_x402_11_request_meta_in_chain_id,
        test_x402_12_self_test,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            import traceback; traceback.print_exc()
            print(f"  ❌ FAIL {t.__name__}: {e}")
    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} PASSED")
