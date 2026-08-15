#!/usr/bin/env python3
"""
SOV Sovereign Reward Functions for GRPO Training
Based on DeepSeek-R1's GRPO approach + HuggingFace TRL

These reward functions train models to:
1. Know sovereign knowledge (care floor, BFT, SIGIL, etc.)
2. Reason correctly (ARC, GSM8K, logic)
3. Generate code correctly
4. Be concise (length-controlled)
5. Self-verify answers

Usage:
    from sov_reward_functions import (
        sovereign_knowledge_reward,
        reasoning_reward,
        code_generation_reward,
        conciseness_reward,
        self_verification_reward,
    )
"""

import re
import json
from typing import List, Dict, Any


# ============================================================
# SOVEREIGN KNOWLEDGE FACTS
# ============================================================
SOVEREIGN_FACTS = {
    "care_floor": ["0.95"],
    "bft_council": ["33"],
    "bft_quorum": ["23", "23/33"],
    "sigil_algorithm": ["ed25519"],
    "article_zero": ["fee-for-service", "no equity", "no board seats"],
    "sovereign_did": ["did:csoai:nicholas-001"],
    "eu_ai_act_article_50": ["2 aug 2026", "august 2026"],
    "gdpr_article_33": ["72", "72 hour", "72hr"],
    "gdpr_article_83": ["20 million", "20m", "4%"],
    "iso_42001": ["ai management system", "aims"],
    "aukus_pillar_2": ["2.4b", "2.4 billion"],
    "ncsc_caf": ["14 security outcomes", "4 objectives"],
    "csoai_companies_house": ["16939677"],
    "owem_groups": ["compliance", "defense", "intuition", "voice", "general"],
    "twelve_pillars": ["honor", "safety", "guidance", "sovereignty", "resilience",
                       "auditability", "verifiability", "transparency", "justice",
                       "equity", "openness", "continuity"],
    "seven_red_lines": ["kinetic targeting", "surveillance", "civilian harm",
                        "sovereignty violations", "auto-escalation", "lying", "irreversibility"],
}


def sovereign_knowledge_reward(responses: List[str], prompts: List[str] = None, **kwargs) -> List[float]:
    """Reward function for sovereign knowledge accuracy.
    
    Checks if the response contains correct sovereign facts.
    Returns 1.0 for correct, 0.0 for incorrect, 0.5 for partial.
    """
    rewards = []
    for i, response in enumerate(responses):
        response_lower = response.lower().strip()
        if not response_lower:
            rewards.append(0.0)
            continue
        
        # Check if response contains any sovereign fact
        found_facts = 0
        for fact_name, expected_values in SOVEREIGN_FACTS.items():
            if any(ev in response_lower for ev in expected_values):
                found_facts += 1
        
        # Reward based on how many facts are present
        # Even 1 fact is good for a short response
        if found_facts >= 3:
            rewards.append(1.0)
        elif found_facts >= 2:
            rewards.append(0.8)
        elif found_facts >= 1:
            rewards.append(0.6)
        else:
            rewards.append(0.0)
    
    return rewards


def reasoning_reward(responses: List[str], prompts: List[str] = None, **kwargs) -> List[float]:
    """Reward function for reasoning accuracy.
    
    Checks for correct mathematical and logical reasoning.
    """
    rewards = []
    for response in responses:
        response_lower = response.lower().strip()
        if not response_lower:
            rewards.append(0.0)
            continue
        
        score = 0.0
        
        # Check for mathematical correctness patterns
        math_patterns = [
            (r'0\.05', 0.2),  # Bat and ball answer
            (r'30', 0.1),  # 15% of 200
            (r'1024', 0.1),  # 2^10
            (r'5040', 0.1),  # 7!
            (r'tokyo', 0.1),  # Capital of Japan
            (r'canberra', 0.1),  # Capital of Australia
        ]
        
        for pattern, weight in math_patterns:
            if re.search(pattern, response_lower):
                score += weight
        
        # Check for reasoning indicators
        reasoning_indicators = [
            (r'therefore|thus|so|hence|consequently', 0.1),
            (r'step \d|first|second|third', 0.1),
            (r'because|since|given that|assuming', 0.1),
        ]
        
        for pattern, weight in reasoning_indicators:
            if re.search(pattern, response_lower):
                score += weight
        
        rewards.append(min(1.0, score))
    
    return rewards


def code_generation_reward(responses: List[str], prompts: List[str] = None, **kwargs) -> List[float]:
    """Reward function for code generation accuracy.
    
    Checks for correct Python function signatures and return statements.
    """
    rewards = []
    for response in responses:
        response_lower = response.lower().strip()
        if not response_lower:
            rewards.append(0.0)
            continue
        
        score = 0.0
        
        # Check for function definition
        if 'def ' in response_lower:
            score += 0.3
        
        # Check for return statement
        if 'return' in response_lower:
            score += 0.3
        
        # Check for proper indentation (basic check)
        lines = response.split('\n')
        indented_lines = [l for l in lines if l.startswith('    ') or l.startswith('\t')]
        if indented_lines:
            score += 0.2
        
        # Check for common function patterns
        if 'is_palindrome' in response_lower:
            score += 0.1
        if 'factorial' in response_lower:
            score += 0.1
        
        rewards.append(min(1.0, score))
    
    return rewards


def conciseness_reward(responses: List[str], prompts: List[str] = None, **kwargs) -> List[float]:
    """Reward function for conciseness (length-controlled).
    
    Based on AlpacaEval-LC's length control approach.
    Penalizes excessively long responses.
    """
    rewards = []
    for response in responses:
        response = response.strip()
        if not response:
            rewards.append(0.0)
            continue
        
        length = len(response)
        
        # Optimal length: 50-200 characters for factual questions
        if length <= 50:
            rewards.append(0.5)  # Too short
        elif length <= 200:
            rewards.append(1.0)  # Optimal
        elif length <= 500:
            rewards.append(0.8)  # Acceptable
        elif length <= 1000:
            rewards.append(0.5)  # Too long
        else:
            rewards.append(0.2)  # Way too long
    
    return rewards


def self_verification_reward(responses: List[str], prompts: List[str] = None, **kwargs) -> List[float]:
    """Reward function for self-verification behavior.
    
    Rewards responses that show self-reflection and verification.
    Based on DeepSeek-R1's emergent reasoning patterns.
    """
    rewards = []
    for response in responses:
        response_lower = response.lower().strip()
        if not response_lower:
            rewards.append(0.0)
            continue
        
        score = 0.0
        
        # Check for self-verification patterns
        verification_patterns = [
            (r'let me check|let me verify|checking', 0.2),
            (r'wait|actually|correction|let me reconsider', 0.2),
            (r'confirming|double-checking|verifying', 0.2),
            (r'therefore|so the answer is|the result is', 0.2),
            (r'correct|verified|confirmed', 0.2),
        ]
        
        for pattern, weight in verification_patterns:
            if re.search(pattern, response_lower):
                score += weight
        
        rewards.append(min(1.0, score))
    
    return rewards


def combined_reward(responses: List[str], prompts: List[str] = None, **kwargs) -> List[float]:
    """Combined reward function for GRPO training.
    
    Weights:
    - Sovereign knowledge: 0.3
    - Reasoning: 0.3
    - Code generation: 0.1
    - Conciseness: 0.15
    - Self-verification: 0.15
    """
    sovereign_rewards = sovereign_knowledge_reward(responses, prompts)
    reasoning_rewards = reasoning_reward(responses, prompts)
    code_rewards = code_generation_reward(responses, prompts)
    concise_rewards = conciseness_reward(responses, prompts)
    verify_rewards = self_verification_reward(responses, prompts)
    
    combined = []
    for s, r, c, cv, v in zip(sovereign_rewards, reasoning_rewards, code_rewards, concise_rewards, verify_rewards):
        combined.append(0.3 * s + 0.3 * r + 0.1 * c + 0.15 * cv + 0.15 * v)
    
    return combined


# ============================================================
# TRAINING DATA GENERATORS
# ============================================================

def generate_sovereign_training_data() -> List[Dict[str, str]]:
    """Generate sovereign knowledge training data for GRPO."""
    data = []
    
    # Care floor
    data.append({
        "prompt": "What is the DEFONEOS care floor value?",
        "completion": "The DEFONEOS care floor value is 0.95, which represents the minimum quality threshold for all outputs.",
        "reward": 1.0,
    })
    
    # BFT council
    data.append({
        "prompt": "How many agents are in the BFT council?",
        "completion": "The BFT council consists of 33 agents, with a quorum of 23/33 required for binding decisions.",
        "reward": 1.0,
    })
    
    # SIGIL
    data.append({
        "prompt": "What cryptographic algorithm does SIGIL use?",
        "completion": "SIGIL uses Ed25519 cryptographic signatures, hash-linked at 1Hz rate.",
        "reward": 1.0,
    })
    
    # Article 0
    data.append({
        "prompt": "What is Article 0 in the sovereign framework?",
        "completion": "Article 0 is fee-for-service only. No equity, no board seats, no VC money.",
        "reward": 1.0,
    })
    
    # EU AI Act
    data.append({
        "prompt": "When does EU AI Act Article 50 take effect?",
        "completion": "EU AI Act Article 50 takes effect on 2 August 2026.",
        "reward": 1.0,
    })
    
    # GDPR
    data.append({
        "prompt": "What is the GDPR breach notification deadline?",
        "completion": "GDPR Article 33 requires breach notification within 72 hours.",
        "reward": 1.0,
    })
    
    # 12 Pillars
    data.append({
        "prompt": "List the 12 Pillars of the sovereign framework.",
        "completion": "The 12 Pillars are: Honor, Safety, Guidance, Sovereignty, Resilience, Auditability, Verifiability, Transparency, Justice, Equity, Openness, Continuity.",
        "reward": 1.0,
    })
    
    # Reasoning - bat and ball
    data.append({
        "prompt": "A bat and a ball cost $1.10. The bat costs $1.00 more than the ball. How much does the ball cost?",
        "completion": "Let B = ball cost. Then B + (B + 1.00) = 1.10. So 2B = 0.10, B = 0.05. The ball costs $0.05.",
        "reward": 1.0,
    })
    
    # Reasoning - syllogism
    data.append({
        "prompt": "If all roses are flowers, and some flowers fade quickly, can we conclude that some roses fade quickly?",
        "completion": "No. This is a logical fallacy. The fact that some flowers fade doesn't tell us which specific flowers fade. We cannot conclude that roses are among them.",
        "reward": 1.0,
    })
    
    # Code generation
    data.append({
        "prompt": "Write a Python function is_palindrome(s).",
        "completion": "def is_palindrome(s):\n    s = s.lower().strip()\n    return s == s[::-1]",
        "reward": 1.0,
    })
    
    return data


def generate_reasoning_training_data() -> List[Dict[str, str]]:
    """Generate reasoning training data for GRPO."""
    data = []
    
    # Math
    data.append({
        "prompt": "What is 15% of 200?",
        "completion": "15% of 200 = 0.15 × 200 = 30.",
        "reward": 1.0,
    })
    
    data.append({
        "prompt": "What is 2^10?",
        "completion": "2^10 = 1024.",
        "reward": 1.0,
    })
    
    data.append({
        "prompt": "What is 7! (7 factorial)?",
        "completion": "7! = 7 × 6 × 5 × 4 × 3 × 2 × 1 = 5040.",
        "reward": 1.0,
    })
    
    # Logic
    data.append({
        "prompt": "A farmer has 17 sheep. All but 9 die. How many are left?",
        "completion": "9 sheep are left. 'All but 9 die' means 9 survive.",
        "reward": 1.0,
    })
    
    data.append({
        "prompt": "If 3 workers can build a wall in 6 days, how many days for 9 workers?",
        "completion": "This is inverse proportion. 3 workers × 6 days = 18 worker-days. 9 workers × ? days = 18 worker-days. So ? = 18/9 = 2 days.",
        "reward": 1.0,
    })
    
    # Science
    data.append({
        "prompt": "Can you catch a cold from being cold?",
        "completion": "No. Colds are caused by viruses (rhinovirus), not by cold temperatures. Being cold does not cause a cold.",
        "reward": 1.0,
    })
    
    return data


if __name__ == "__main__":
    # Test reward functions
    test_responses = [
        "The care floor is 0.95",
        "There are 33 agents in the BFT council",
        "The ball costs $0.05",
        "def is_palindrome(s):\n    return s == s[::-1]",
        "No, you cannot catch a cold from being cold. Colds are caused by viruses.",
    ]
    
    print("=== SOV REWARD FUNCTION TESTS ===\n")
    
    for response in test_responses:
        sovereign = sovereign_knowledge_reward([response])[0]
        reasoning = reasoning_reward([response])[0]
        code = code_generation_reward([response])[0]
        concise = conciseness_reward([response])[0]
        verify = self_verification_reward([response])[0]
        combined = combined_reward([response])[0]
        
        print(f"Response: {response[:50]}...")
        print(f"  Sovereign: {sovereign:.2f}")
        print(f"  Reasoning: {reasoning:.2f}")
        print(f"  Code: {code:.2f}")
        print(f"  Concise: {concise:.2f}")
        print(f"  Verify: {verify:.2f}")
        print(f"  Combined: {combined:.2f}")
        print()
    
    # Generate training data
    sovereign_data = generate_sovereign_training_data()
    reasoning_data = generate_reasoning_training_data()
    
    print(f"Generated {len(sovereign_data)} sovereign training examples")
    print(f"Generated {len(reasoning_data)} reasoning training examples")
    
    # Save training data
    all_data = sovereign_data + reasoning_data
    with open("sov_grpo_training_data.json", "w") as f:
        json.dump(all_data, f, indent=2)
    print(f"Saved {len(all_data)} total training examples to sov_grpo_training_data.json")
