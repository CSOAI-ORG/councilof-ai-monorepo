"""SOVOS command-line interface: score a governance record from JSON."""
from __future__ import annotations

import json
import sys

from .gspc import compliance_matrix, score_gspc


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        print(
            "sovos: SOVOS governance scorer (ETSI EN 304 223 / GSPC)\n\n"
            "Usage:\n"
            "  sovos matrix                # print the 13-principle compliance matrix\n"
            "  sovos score <record.json>   # score a governance record (JSON file)\n"
            "  sovos score -               # read record JSON from stdin\n"
        )
        return 0

    if argv[0] == "matrix":
        for row in compliance_matrix():
            print(f"[{row['id']}] {row['title']} ({'|'.join(row['axes'])})")
            print(f"      {row['description']}")
        return 0

    if argv[0] == "score":
        if len(argv) < 2:
            print("error: score needs a JSON file path or '-' for stdin", file=sys.stderr)
            return 2
        raw = sys.stdin.read() if argv[1] == "-" else open(argv[1]).read()
        record = json.loads(raw)
        result = score_gspc(record).report()
        print(json.dumps(result, indent=2))
        return 0

    print(f"error: unknown command '{argv[0]}'", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
