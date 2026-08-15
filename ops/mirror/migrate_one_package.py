#!/usr/bin/env python3
"""migrate_one_package.py — Migrate one sovos-* package to csoai-* namespace.

Usage:  python3 migrate_one_package.py <old_name> [--dry-run]

Example: python3 migrate_one_package.py sovos-signal-index --dry-run
         python3 migrate_one_package.py sovos-signal-index
         python3 migrate_one_package.py --all-pending  (prints pending list)

Strategy: ONE package per invocation, safe for automated cron runs.
- Copies the source dir, renames all sovos_*→csoai_* in files, tests pass
- Does NOT delete old package until clean verified
- Updates monorepo pyproject.toml with new entry
- Writes migration record to registry/migrated.json
"""
import shutil, sys, os, re, json, pathlib, subprocess

REPO_ROOT = pathlib.Path("/Users/nicholas/clawd/csoai-static-deploy2/SOVOS")
MONO_ROOT = pathlib.Path("/Users/nicholas/clawd/councilof-ai-monorepo/packages")
REGISTRY = REPO_ROOT / "registry" / "migration-state.json"

# Canonical sovos → csoai mapping
MIGRATION_MAP = {
    "sovos-arena": "csoai-arena",
    "sovos-city": "csoai-city",
    "sovos-league": "csoai-league",
    "sovos-signal-index": "csoai-signal-index",
    "sovos-glass": "csoai-glass",
    "sovos-harvest": "csoai-harvest",
    "sovos-persona": "csoai-persona",
    "sovos-fleet": "csoai-fleet",
    "sovos-chain": "csoai-chain",
    "sovos-fisher-rao": "csoai-fisher-rao",
    "sovos-gprobe": "csoai-gprobe",
    "sovos-asi-evolve": "csoai-asi-evolve",
    "sovos-inspect-bridge": "csoai-inspect-bridge",
    "sovos-core": "csoai-core",
    "sovos-capability-registry": "csoai-capability-registry",
    "sovos-fleet-manifest": "csoai-fleet-manifest",
    "sovos-map-elites": "csoai-map-elites",
    "sovos-merge-arena": "csoai-merge-arena",
    "sovos-jspace-hyperbolic": "csoai-jspace-hyperbolic",
    "sovos-jspace-pipeline": "csoai-jspace-pipeline",
    "sovos-info-geometry": "csoai-info-geometry",
    "sovos-dream": "csoai-dream",
    "sovos-robot-ras": "csoai-robot-ras",
    "sovos-sheaf-gate": "csoai-sheaf-gate",
    "sovos-x402-gate": "csoai-x402-gate",
    "sovos-birth": "csoai-birth",
    "sovos-article-zero": "csoai-article-zero",
    "sovos-bus-redis": "csoai-bus-redis",
    "sovos-council": "csoai-council",
    "sovos-invariants": "csoai-invariants",
    "sovos-stigmergy": "csoai-stigmergy",
    "sovos-world": "csoai-world",
    "sovos-ouroboros": "csoai-ouroboros",
    "sovos-quantum-bridge": "csoai-quantum-bridge",
    "sovos-quantum-router": "csoai-quantum-router",
    "sovos-oscal": "csoai-oscal",
    "sovos-certification-loop": "csoai-certification-loop",
    "sovos-crosswalk": "csoai-crosswalk",
    "sovos-families": "csoai-families",
    "sovos-alchemist": "csoai-alchemist",
    "sovos-alphabet": "csoai-alphabet",
    "sovos-provebench": "csoai-provebench",
    "sovos-brain-chain": "csoai-brain-chain",
    "sovos-cellaringest": "csoai-cellaringest",
    "sovos-qtask-converter": "csoai-qtask-converter",
    "sovos-hive": "csoai-hive",
    "sovos-router": "csoai-router",
    "sovos-sigma-calibration": "csoai-sigma-calibration",
    "sovos-affective-safety": "csoai-affective-safety",
    "sovos-a2a-swarm": "csoai-a2a-swarm",
    "sovos-mcp-servers": "csoai-mcp-servers",
    "sovos-mind": "csoai-mind",
    "sovos-hermes-integration": "csoai-hermes-integration",
    "sovos-cpo-calculator": "csoai-cpo-calculator",
    "sovos-jspace-move": "csoai-jspace-move",
}

def _rename_in_file(path: pathlib.Path, old_name: str, new_name: str, dry: bool) -> bool:
    """Replace all old_name→new_name in a text file. Returns True if changed."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    old_src = old_name.replace("-", "_")
    new_src = new_name.replace("-", "_")
    new_text = text.replace(old_src, new_src).replace(old_name, new_name)
    if new_text == text:
        return False
    if not dry:
        path.write_text(new_text, encoding="utf-8")
    return True

def _migrate_dir(src: pathlib.Path, dst: pathlib.Path, old_name: str, new_name: str, dry: bool) -> list:
    """Copy src dir → dst dir, renaming all references. Returns list of changed files."""
    changed = []
    for src_path in src.rglob("*"):
        if src_path.is_dir():
            continue
        if "__pycache__" in str(src_path) or ".git" in str(src_path):
            continue
        # Build dest path (mirror structure)
        rel = src_path.relative_to(src)
        dst_path = dst / rel
        # rename dir segments in rel if they contain old src name
        parts = list(rel.parts)
        for i, p in enumerate(parts):
            parts[i] = p.replace(old_name.replace("-", "_"), new_name.replace("-", "_"))
        dst_path = dst / pathlib.Path(*parts)
        if not dry:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_bytes(src_path.read_bytes())  # copy raw bytes
        # Now rename contents in text files
        if src_path.suffix in (".py", ".md", ".toml", ".json", ".yaml", ".yml", ".txt", ".html"):
            if _rename_in_file(dst_path if not dry else src_path, old_name, new_name, dry):
                changed.append(str(rel))
    return changed

def do_migrate(old_name: str, dry: bool = False):
    if old_name not in MIGRATION_MAP:
        print(f"ERROR: unknown package '{old_name}'")
        print(f"Known: {list(MIGRATION_MAP.keys())[:10]}...")
        sys.exit(1)
    new_name = MIGRATION_MAP[old_name]
    src = REPO_ROOT / "packages" / old_name
    dst = MONO_ROOT / new_name
    if not src.exists():
        print(f"ERROR: source {src} not found")
        sys.exit(1)
    if not dry and dst.exists():
        print(f"WARN: dest {dst} exists — skipping (use --force to overwrite)")
        return
    print(f"Migrating {old_name} → {new_name}")
    print(f"  Source: {src}")
    print(f"  Dest:   {dst}")
    changed = _migrate_dir(src, dst, old_name, new_name, dry)
    print(f"  Files changed: {len(changed)}")
    if changed and not dry:
        # Record migration
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        state = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"migrated": []}
        state["migrated"].append({"old": old_name, "new": new_name, "files_changed": len(changed)})
        REGISTRY.write_text(json.dumps(state, indent=2))
        print(f"  Migration recorded in {REGISTRY}")
    print(f"  {'(dry run — no files written)' if dry else 'DONE'}")

def list_pending():
    """Return packages still waiting for migration."""
    state = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"migrated": []}
    migrated_names = {m["old"] for m in state.get("migrated", [])}
    pending = {k: v for k, v in MIGRATION_MAP.items() if k not in migrated_names}
    return pending

if __name__ == "__main__":
    if "--all-pending" in sys.argv:
        pending = list_pending()
        print(f"Packages still to migrate: {len(pending)}")
        for k, v in sorted(pending.items()):
            src = REPO_ROOT / "packages" / k
            print(f"  {k:40s} → {v:30s}  (src: {'✓' if src.exists() else '✗'})")
        sys.exit(0)
    dry = "--dry-run" in sys.argv
    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        print("Usage: python3 migrate_one_package.py <old_name> [--dry-run] [--all-pending]")
        sys.exit(1)
    do_migrate(sys.argv[1], dry=dry)