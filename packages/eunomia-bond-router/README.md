# eunomia-bond-router
Bridge 1 of EUNOMIA — COBOL → A2A. Reads a COBOL COPYBOOK, parses flat records into JSON,
signs each record (Ed25519, `did:web:csoai.org#estate-chain-1`), and emits an A2A agent card.
The "$130T proof of weave": the COPYBOOK (the meal) becomes an attestable JSON (energy an A2A
agent can consume).

## How it works
`COBOL COPYBOOK → (cobol_parser) → JSON schema + records → (attest) → signed A2A attestation → agent card`

## Files
- `cobol_parser.py` — COPYBOOK → field/layout; flat record → JSON
- `attest.py` — sign a record JSON → Ed25519 A2A attestation
- `a2a_card.py` — the agent card

## Test
```
python3 -c "import sys;sys.path.insert(0,'src');from eunomia_bond_router.cobol_parser import *;l=parse_copybook('01 R.\n 05 ID PIC X(10).\n 05 AMT PIC 9(8)V99.');print(parse_record('1234567890'+'0000001234', l))"
```
