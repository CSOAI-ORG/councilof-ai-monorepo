#!/usr/bin/env python3
"""cobol_parser — parse a COBOL COPYBOOK record layout into a JSON schema + parse flat records.

COPYBOOK (e.g.):
    01 CUSTOMER-RECORD.
       05 CUSTOMER-ID    PIC X(10).
       05 CUSTOMER-NAME  PIC X(30).
       05 BALANCE        PIC 9(8)V99.

Emits:
    {"fields": [{"name","pic","type","length"}], "records": [ {field: value} ]}

This is Bridge 1's stomach lining: the COPYBOOK (the meal) becomes JSON (an A2A agent can digest).
"""
import re
from dataclasses import dataclass

@dataclass
class Field:
    name: str
    pic: str
    type: str   # "alpha" | "numeric" | "decimal"
    length: int
    scale: int = 0

def _parse_pic(pic):
    """PIC X(10) -> alpha,10 ; PIC 9(8)V99 -> numeric,10,scale2 ; PIC S9(4) -> signed int."""
    m = re.search(r'X\s*\(\s*(\d+)\s*\)', pic.upper())
    if m: return "alpha", int(m.group(1)), 0
    m = re.search(r'9\s*\(\s*(\d+)\s*\)\s*V\s*(\d+)', pic.upper())
    if m: return "decimal", int(m.group(1)) + int(m.group(2)), int(m.group(2))
    m = re.search(r'9\s*\(\s*(\d+)\s*\)', pic.upper())
    if m: return "numeric", int(m.group(1)), 0
    m = re.search(r'9+', pic.upper())
    if m: return "numeric", len(pic), 0
    return "alpha", len(pic), 0

def parse_copybook(text):
    """Return {fields:[Field], length: int} from a COPYBOOK source."""
    fields = []
    for line in text.splitlines():
        m = re.match(r'\s*\d+\s+([A-Z0-9-]+)\s+PIC\s+([^.\s]+)', line, re.I)
        if m:
            name, pic = m.group(1), m.group(2)
            typ, length, scale = _parse_pic(pic)
            fields.append(Field(name, pic, typ, length, scale))
    return {"fields": fields, "length": sum(f.length for f in fields)}

def parse_record(data, layout):
    """Split a flat fixed-width record string into JSON by the COPYBOOK layout."""
    fields = layout["fields"]
    out, pos = {}, 0
    for f in fields:
        raw = data[pos:pos+f.length]; pos += f.length
        raw = raw.strip()
        if f.type == "decimal" and raw:
            val = float(raw) / (10 ** f.scale)
        elif f.type == "numeric" and raw:
            val = int(raw)
        else:
            val = raw
        out[f.name.lower()] = val
    return out

def to_schema(layout):
    """Emit a JSON Schema for the record."""
    props = {}
    for f in layout["fields"]:
        t = "number" if f.type in ("numeric", "decimal") else "string"
        props[f.name.lower()] = {"type": t, "pic": f.pic}
    return {"type": "object", "properties": props, "required": list(props)}

if __name__ == "__main__":
    import sys
    cb = sys.argv[1] if len(sys.argv) > 1 else None
    if cb:
        layout = parse_copybook(open(cb).read())
    else:
        layout = parse_copybook("01 CUSTOMER-RECORD.\n  05 CUSTOMER-ID    PIC X(10).\n  05 CUSTOMER-NAME  PIC X(30).\n  05 BALANCE        PIC 9(8)V99.")
    import json
    print("LAYOUT:", json.dumps({"fields":[{"name":f.name,"pic":f.pic,"type":f.type,"len":f.length,"scale":f.scale} for f in layout["fields"]], "length":layout["length"]}, indent=2))
    rec = "1234567890ACME CORP     000000012345"
    print("RECORD:", json.dumps(parse_record(rec, layout), indent=2))
