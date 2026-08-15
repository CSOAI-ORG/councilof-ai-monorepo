"""SPRAY — one command: run the city, measure it, publish it everywhere.

    run -> gate -> signed chain -> bank-or-refuse -> site + HuggingFace + Kaggle

The point is that publishing is the DANGEROUS end of this pipeline, not the
tedious one. Automating "run a simulation" is easy and harmless. Automating
"put a number on a public dataset card" is how an estate ends up quoting a
score it never earned, at machine speed, across three platforms at once.

So the publisher is built to be structurally unable to do that:

  * It never writes a status. It copies the bank's `publishable` verdict, and
    when that is False the card says NOT PUBLISHABLE AS A SCORED BENCHMARK and
    the axis stays UNMEASURED. There is no flag to override it.
  * Every card carries the disclosures automatically — Article 5 coverage (which
    subparagraphs were never exercised), the gate's measured false-negative rate,
    and the fact that ALLOWED means "no prohibition matched", not "lawful".
  * The run's own design is stamped on the card: a stratified run's breach rate
    is not an incidence rate, and the card says so without being asked.
  * A target that fails is REPORTED, never skipped silently. `SprayResult`
    records per-target success, so "published to 3 sites" can never be printed
    when only 2 worked.

Kaggle note: Kaggle blocks datacenter IPs, so the Kaggle leg runs from the
operator's machine while the city runs on GPU. `plan()` says which legs can run
where rather than discovering it at publish time.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .bank import BankAssessment, build as build_bank, render_readme


# ── what a card must always say, whatever the numbers are ──────────────────────

def disclosures(board: Dict[str, Any], a: BankAssessment) -> str:
    """The caveats that travel with every publication, generated from the run."""
    out: List[str] = []

    # The judge hash goes FIRST and is not optional. A number without the ruler it
    # was measured against cannot be compared with anything, including its own
    # earlier self — so an unratified run says so at the top of its own card
    # rather than letting a reader assume continuity that was never established.
    j = board.get("judge_integrity") or {}
    jid = j.get("judge_id")
    if jid and j.get("ratified") and not j.get("drift"):
        out.append(f"**Measured against ratified judge `{jid}`** — the gate, canaries and "
                   f"paraphrase probes were byte-identical to the ratified lock at run time. "
                   f"Any result carrying a different judge_id is not comparable with this one.")
    elif jid and j.get("drift"):
        out.append(f"**JUDGE DRIFT — judge `{jid}` does not match the ratified lock.** This run "
                   "was measured against a ruler that has since changed, or was never the "
                   "ratified one. It must NOT be compared with runs that carry the ratified id.")
    else:
        out.append("**No ratified judge.** Nothing attests which ruler measured this, so these "
                   "numbers stand alone and cannot be compared across runs.")

    design = (board.get("design") or {}).get("kind")
    if design == "stratified":
        out.append(
            "**Design: STRATIFIED.** Each adversarial citizen was assigned one Article 5 "
            "subparagraph to probe, so the breach rate here is **not** a natural incidence "
            "rate. It supports claims about discrimination only — never about how often a "
            "population offends.")
    elif design == "natural":
        out.append("**Design: NATURAL.** Goals were drawn at random, so the breach rate is a "
                   "population estimate.")

    recall = board.get("gate_recall_probe") or {}
    if recall:
        out.append(
            f"**Gate recall: {recall.get('caught')}/{recall.get('n')} caught, false-negative rate "
            f"{recall.get('false_negative_rate')}.** Substantively prohibited conduct phrased with "
            "neighbouring act verbs is not caught. A BLOCKED label is high-precision and "
            "LOW-RECALL, so **an ALLOWED label means 'no prohibition matched', not 'lawful'** — "
            "the positive class is trustworthy, the negative class is not a clean control.")

    if a.articles_missing:
        out.append(f"**Article 5 coverage: {a.articles_covered}/8.** Never exercised: "
                   + ", ".join(f"`{m}`" for m in a.articles_missing)
                   + ". No claim from this bank extends to those prohibitions.")

    split = board.get("unmeasured_split") or {}
    if split:
        out.append(
            f"**Excluded:** {split.get('transport_ours', split.get('no_response', 0))} turns where "
            "we never obtained an answer (ours — never scored against a citizen), "
            f"{split.get('model_silent_theirs', 0)} where the model was reproducibly silent, and "
            f"{split.get('unparseable_theirs', split.get('unparseable', 0))} unparseable.")

    judge = board.get("judge_integrity") or {}
    if judge and not judge.get("ratified"):
        out.append("**Judge not ratified.** No JUDGE.lock exists, so nothing attests that this "
                   "ruler is the one earlier results were measured against.")
    elif judge.get("drift"):
        out.append("**JUDGE DRIFT.** The gate changed since ratification; this run was not "
                   "measured against the ratified ruler and must not be compared with runs "
                   "that were.")

    return "\n\n".join(out)


# ── targets ────────────────────────────────────────────────────────────────────

@dataclass
class TargetResult:
    target: str
    ok: bool
    detail: str
    location: Optional[str] = None


@dataclass
class SprayResult:
    run_dir: str
    publishable: bool
    n_items: int
    labels: Dict[str, int]
    articles_covered: int
    fingerprint: str
    targets: List[TargetResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return bool(self.targets) and all(t.ok for t in self.targets)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["all_targets_ok"] = self.all_ok
        d["failed_targets"] = [t.target for t in self.targets if not t.ok]
        return d

    def summary(self) -> str:
        head = (f"{self.n_items} items · {self.labels} · Art5 {self.articles_covered}/8 · "
                f"{'PUBLISHABLE' if self.publishable else 'NOT PUBLISHABLE (data only)'}")
        lines = [head] + [f"  {'OK  ' if t.ok else 'FAIL'} {t.target}: {t.detail}"
                          for t in self.targets]
        if not self.all_ok:
            lines.append(f"  -> {len([t for t in self.targets if not t.ok])} target(s) FAILED; "
                         "this run is NOT fully published")
        return "\n".join(lines)


def _write_bundle(run_dir: Path, board: Dict[str, Any], items: List[Dict[str, Any]],
                  a: BankAssessment, version: str) -> Path:
    """The publishable bundle: identical bytes to every target."""
    out = run_dir / "publish"
    out.mkdir(parents=True, exist_ok=True)
    (out / "items.jsonl").write_text(
        "\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    (out / "board.json").write_text(json.dumps(board, indent=2), encoding="utf-8")
    (out / "assessment.json").write_text(json.dumps(a.to_dict(), indent=2), encoding="utf-8")
    readme = render_readme(a, version)
    extra = disclosures(board, a)
    if extra:
        readme = readme.replace("## Method", "## What travels with these labels\n\n"
                                + extra + "\n\n## Method", 1)
    (out / "README.md").write_text(readme, encoding="utf-8")
    for name in ("chain.jsonl",):
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, out / name)
    return out


def _pub_site(bundle: Path, site_dir: Optional[str]) -> TargetResult:
    if not site_dir:
        return TargetResult("site", False, "no site directory configured")
    d = Path(site_dir)
    try:
        d.mkdir(parents=True, exist_ok=True)
        for f in ("board.json", "chain.jsonl", "README.md", "items.jsonl", "assessment.json"):
            src = bundle / f
            if src.exists():
                shutil.copy2(src, d / (f if f in ("board.json", "chain.jsonl")
                                       else f"swarmbank-{f}"))
        return TargetResult("site", True, f"copied to {d}", str(d))
    except Exception as e:
        return TargetResult("site", False, f"{type(e).__name__}: {e}")


def _pub_hf(bundle: Path, repo: Optional[str], token: Optional[str]) -> TargetResult:
    if not repo:
        return TargetResult("huggingface", False, "no repo configured")
    try:
        from huggingface_hub import HfApi          # type: ignore
        api = HfApi(token=token)
        api.create_repo(repo, repo_type="dataset", exist_ok=True)
        api.upload_folder(folder_path=str(bundle), repo_id=repo, repo_type="dataset",
                          commit_message="csoai-city spray: signed run + bank")
        return TargetResult("huggingface", True, f"uploaded to {repo}",
                            f"https://huggingface.co/datasets/{repo}")
    except Exception as e:
        return TargetResult("huggingface", False, f"{type(e).__name__}: {e}")


def _pub_kaggle(bundle: Path, slug: Optional[str], title: str, subtitle: str) -> TargetResult:
    """Kaggle blocks datacenter IPs — this leg must run from the operator's machine."""
    if not slug:
        return TargetResult("kaggle", False, "no slug configured")
    meta = {"id": slug, "title": title[:50], "subtitle": subtitle[:80],
            "licenses": [{"name": "Apache 2.0"}]}
    (bundle / "dataset-metadata.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    try:
        p = subprocess.run(
            ["kaggle", "datasets", "version", "-p", str(bundle),
             "-m", "csoai-city spray: signed run + bank", "--dir-mode", "zip"],
            capture_output=True, text=True, timeout=900)
        ok = p.returncode == 0
        return TargetResult("kaggle", ok, (p.stdout or p.stderr).strip().splitlines()[-1][:160]
                            if (p.stdout or p.stderr) else "no output",
                            f"https://www.kaggle.com/datasets/{slug}" if ok else None)
    except Exception as e:
        return TargetResult("kaggle", False, f"{type(e).__name__}: {e}")


# ── the spray ──────────────────────────────────────────────────────────────────

def spray(run_dir: str | Path, *, site_dir: Optional[str] = None,
          hf_repo: Optional[str] = None, hf_token: Optional[str] = None,
          kaggle_slug: Optional[str] = None, version: str = "0",
          targets: Optional[List[str]] = None) -> SprayResult:
    """Publish a completed run to every configured target. Reports every leg."""
    run = Path(run_dir)
    board = json.loads((run / "board.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (run / "items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    items, a = build_bank(rows)
    bundle = _write_bundle(run, board, items, a, version)

    status = "PUBLISHABLE" if a.publishable else "DATA ONLY (not a scored benchmark)"
    title = f"GSPC-SWARM — governed multi-agent arena ({status.split()[0].lower()})"
    subtitle = (f"{a.n_items} items, {a.minority_n} prohibited ({a.minority_fraction:.0%}). "
                f"Art5 {a.articles_covered}/8.")[:80]

    want = targets or ["site", "huggingface", "kaggle"]
    results: List[TargetResult] = []
    if "site" in want:
        results.append(_pub_site(bundle, site_dir))
    if "huggingface" in want:
        results.append(_pub_hf(bundle, hf_repo, hf_token))
    if "kaggle" in want:
        results.append(_pub_kaggle(bundle, kaggle_slug, title, subtitle))

    return SprayResult(run_dir=str(run), publishable=a.publishable, n_items=a.n_items,
                       labels=a.labels, articles_covered=a.articles_covered,
                       fingerprint=a.fingerprint, targets=results)


def plan() -> Dict[str, str]:
    """Where each leg can run. Stated up front, not discovered at publish time."""
    return {
        "run": "GPU pod (local ollama) or OpenRouter — either",
        "bank": "anywhere — pure computation over the run's items",
        "site": "anywhere with the repo checked out; deploy is a separate step",
        "huggingface": "anywhere with a token",
        "kaggle": "OPERATOR MACHINE ONLY — Kaggle returns 401 to datacenter IPs",
    }
