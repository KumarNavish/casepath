"""Verify every committed artifact this work depends on. No network, no model calls.

Run from casepath-api/. Exits non-zero on any failure, so it can gate a release.
"""
import json, hashlib, re, sys, unicodedata
from pathlib import Path

R = Path(__file__).resolve().parent
API = R.parent.parent / "casepath-api"
def norm(s): return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()

fails = []

# Manifest is a complete integrity roster for committed JSON analysis artifacts.
manifest_path = R / "artifacts/MANIFEST.json"
manifest = json.loads(manifest_path.read_text())
artifact_files = sorted(p.name for p in (R / "artifacts").glob("*.json") if p.name != "MANIFEST.json")
manifest_files = sorted(manifest)
missing_from_manifest = sorted(set(artifact_files) - set(manifest_files))
missing_on_disk = sorted(set(manifest_files) - set(artifact_files))
if missing_from_manifest: fails.append(f"analysis artifacts missing from manifest: {missing_from_manifest}")
if missing_on_disk: fails.append(f"manifest entries missing on disk: {missing_on_disk}")
manifest_bad=[]
for name, rec in manifest.items():
    q=R / "artifacts" / name
    if not q.is_file(): continue
    data=q.read_bytes()
    got=hashlib.sha256(data).hexdigest()
    if got != rec.get("sha256") or len(data) != rec.get("bytes"):
        manifest_bad.append(name)
print(f"artifact manifest: {len(manifest_files)} entries, {len(missing_from_manifest)} unmanifested, {len(missing_on_disk)} missing, {len(manifest_bad)} hash/size mismatches")
if manifest_bad: fails.append(f"artifact manifest mismatch: {manifest_bad[:5]}")

b = json.loads((API / "casepath_api/corpora/authority/swiss-authority-bundle-v1.json").read_text())
bad = [p["authority_id"] for p in b["passages"]
       if hashlib.sha256(p["exact_text"].encode()).hexdigest() != p["text_sha256"]]
print(f"authority corpus: {len(b['passages'])} passages, {len(bad)} hash mismatches")
if bad: fails.append(f"passage hash mismatch: {bad[:5]}")

pool = {p["authority_id"]: p["exact_text"] for p in b["passages"]}
C = json.loads((R / "reference_contracts/rent_increase.json").read_text())
ev = [(d["decision_id"], e) for d in C["decisions"] for e in d["evidence"]]
miss = [(d, e["authority_id"]) for d, e in ev if e["authority_id"] not in pool]
gate = [(d, e["authority_id"]) for d, e in ev
        if e["authority_id"] in pool and norm(e["quote"]) not in norm(pool[e["authority_id"]])]
print(f"reference contract: {len(C['decisions'])} decisions, {len(ev)} evidence pairs, "
      f"{len(miss)} unknown authorities, {len(gate)} quotes failing the gate")
if miss: fails.append(f"contract cites authorities not in the corpus: {miss[:5]}")
if gate: fails.append(f"contract quotes no longer verbatim: {gate[:5]}")

# the gate is constitutive: the contract must contain no quote that fails it
if C["audit"]["quotes_kept"] != len(ev):
    fails.append(f"audit says {C['audit']['quotes_kept']} quotes kept but the contract holds {len(ev)}")

sp = json.loads((R / "splits/rent_increase_scenario_split.json").read_text())
dev = {c for s in sp["development"] for c in sp["scenarios"][s]}
con = {c for s in sp["confirmatory"] for c in sp["scenarios"][s]}
allc = [c for v in sp["scenarios"].values() for c in v]
print(f"split: {len(sp['scenarios'])} scenarios, {len(allc)} cases ({len(set(allc))} distinct), "
      f"{len(dev)} development / {len(con)} confirmatory, {len(dev & con)} leaked")
if dev & con: fails.append(f"case appears in both development and confirmatory: {sorted(dev & con)[:5]}")
if len(allc) != len(set(allc)): fails.append("a case appears in more than one scenario")

for g in ("INDUCTION_S2_graph.json", "INDUCTION_S2_graph_v2.json"):
    G = json.loads((R / g).read_text())
    nodes = {n["node_id"] for n in G["nodes"]}
    dangling = [t["edge_id"] for t in G["transitions"]
                if t.get("source_node_id") not in nodes or t.get("target_node_id") not in nodes]
    print(f"{g}: {len(G['nodes'])} nodes, {len(G['transitions'])} transitions, {len(dangling)} dangling")
    if dangling: fails.append(f"{g} has transitions to unknown nodes: {dangling[:5]}")

print()
if fails:
    print("FAILED:"); [print("  -", f) for f in fails]; sys.exit(1)
print("all artifact checks passed")
