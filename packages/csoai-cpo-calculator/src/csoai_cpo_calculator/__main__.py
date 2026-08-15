"""CLI: render CPO power savings reports to markdown.

Usage:
    python -m csoai_cpo_calculator [SCENARIO]
    python -m csoai_cpo_calculator all   # render all 4 pre-built scenarios
    python -m csoai_cpo_calculator hyperscale
    python -m csoai_cpo_calculator mid_enterprise
    python -m csoai_cpo_calculator small_edge
    python -m csoai_cpo_calculator sov1_farm
"""
import sys

from csoai_cpo_calculator import compute_savings, SCENARIOS, render_all_scenarios


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: python -m csoai_cpo_calculator [SCENARIO]")
        print(f"Available scenarios: {', '.join(SCENARIOS.keys())}")
        print("Or 'all' to render every scenario.")
        return 0

    target = argv[0]
    if target == "all":
        print(render_all_scenarios())
        return 0
    if target not in SCENARIOS:
        print(f"Unknown scenario '{target}'. Available: {list(SCENARIOS.keys())}")
        return 1
    report = compute_savings(SCENARIOS[target])
    print(report.to_markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
