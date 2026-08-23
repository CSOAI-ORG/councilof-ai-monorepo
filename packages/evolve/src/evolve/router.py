"""The 90/10 router: a frozen split-conformal predicate.

Once :func:`evolve.conformal.calibrate` has frozen a threshold ``q_hat`` at a
target miscoverage ``alpha`` (e.g. ``alpha = 0.10`` -> route ~90% to ``auto``),
the routing decision is a single deterministic comparison. No LLM-as-judge: no
model scores another model at decision time. The nonconformity *score* may be
computed however the operator likes (see :mod:`evolve.scores`), but the gate
itself is pure arithmetic and exactly reproducible.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["route", "Router", "Decision"]

Decision = Literal["auto", "escalate"]


def route(score: float, q_hat: float) -> Decision:
    """Route a single item by comparing its nonconformity ``score`` to ``q_hat``.

    Returns ``"auto"`` (auto-proceed; the ~90% case) iff ``score <= q_hat``,
    otherwise ``"escalate"`` (hand off to a stronger/human reviewer; the ~10%
    case). This is the frozen split-conformal predicate — deterministic and
    reproducible given ``(score, q_hat)``.

    With ``q_hat = +inf`` (calibration could not certify a finite threshold)
    everything routes to ``auto``; with ``q_hat = -inf`` everything escalates.
    """
    return "auto" if score <= q_hat else "escalate"


class Router:
    """A frozen router: bind ``q_hat`` (and its provenance) once, then call.

    The point of freezing is auditability. ``q_hat`` is set at calibration time
    and never mutated; ``alpha`` and ``n_calib`` are carried alongside purely so
    a downstream signed receipt can record *what guarantee this gate encodes*.
    """

    __slots__ = ("q_hat", "alpha", "n_calib")

    def __init__(self, q_hat: float, *, alpha: float | None = None,
                 n_calib: int | None = None) -> None:
        self.q_hat = float(q_hat)
        self.alpha = alpha
        self.n_calib = n_calib

    def decide(self, score: float) -> Decision:
        """Route one item. Alias of :func:`route` bound to this frozen ``q_hat``."""
        return route(score, self.q_hat)

    def __call__(self, score: float) -> Decision:
        return self.decide(score)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (f"Router(q_hat={self.q_hat!r}, alpha={self.alpha!r}, "
                f"n_calib={self.n_calib!r})")
