#!/usr/bin/env python3
"""agent_wallet — eunomia agent economy.

AI agents can't hold bank accounts. This module gives an agent (e.g. a MEOK NPC)
a wallet: credits (USDC/EUN), a reputation SBT credential graph, and staking so it
can quote markets. An agent that exploits a counterparty is slashed. The NPC becomes
a market participant — the MEOK gaming layer trains financial agents.

Measurement, not certification. Deterministic, offline.
"""


class AgentWallet:
    def __init__(self, agent_id, caretaker="did:web:csoai.org#estate-chain-1"):
        self.agent_id = agent_id
        self.caretaker = caretaker
        self.credits = 0.0
        self.stake = 0.0
        self.sbts = []          # [(name, level)]
        self.reputation = 0.0   # 0..1
        self.history = []       # [(event, score)]

    def mint_sbt(self, name, level):
        self.sbts.append((name, level))

    def fund(self, amount):
        self.credits += amount
        return self.credits

    def stake_to_quote(self, amount):
        """Stake credits to guarantee a quote / market-making position."""
        if amount > self.credits:
            raise ValueError("insufficient credits to stake")
        self.credits -= amount
        self.stake += amount
        return self.stake

    def record_trade(self, fair, exploit=False):
        """Reputation up for a fair trade, slash (stake burn) for an exploit."""
        if exploit:
            burn = self.stake * 0.5
            self.stake -= burn
            self.reputation = max(0.0, self.reputation - 0.2)
            self.history.append(("slash", -burn))
            return burn
        self.reputation = min(1.0, self.reputation + (fair * 0.25))
        self.history.append(("trade", fair))
        return 0.0

    def can_participate(self, threshold=0.2):
        """An agent can only quote if it has staked + some reputation."""
        return self.stake > 0 and self.reputation >= threshold

    def summary(self):
        return {
            "agent_id": self.agent_id,
            "credits": round(self.credits, 4),
            "stake": round(self.stake, 4),
            "reputation": round(self.reputation, 4),
            "sbts": [s[0] for s in self.sbts],
            "can_participate": self.can_participate(),
        }


if __name__ == "__main__":
    dragon = AgentWallet("dragonomicon")
    dragon.mint_sbt("Watchdog Level 5", 5)
    dragon.fund(1000)
    dragon.stake_to_quote(200)
    dragon.record_trade(0.95)
    import json
    print("WALLET:", json.dumps(dragon.summary(), indent=2))
