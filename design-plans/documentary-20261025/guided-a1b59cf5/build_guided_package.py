#!/usr/bin/env python3
"""Build a bounded evidence-only release directory from verified final outputs."""
from pathlib import Path
import argparse, json, hashlib, shutil, subprocess, time, gzip
ROOT=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024")
WORK=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024/.runtime/guided-film-20261025")
EXPECTED_SOURCE="a1b59cf5d78662b35790a11cfd2d46851310482d"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def copy(src,dst):
 src=Path(src);dst=Path(dst)
 if not src.is_file():raise ValueError("Missing source: "+str(src))
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--repo",required=True);a=ap.parse_args()
 repo=Path(a.repo);dest=repo/"design-plans/documentary-20261025/guided-a1b59cf5"
 if dest.exists():raise ValueError("Fresh package directory required")
 render=WORK/"final-render";receipt=json.loads((render/"render-receipt.json").read_text())
 plan=json.loads((WORK/"edit-plan-v7.json").read_text())
 assert receipt["status"]=="passed" and not receipt["preview_only"]
 assert receipt["source_commit"]==EXPECTED_SOURCE and receipt["frames"]==plan["frames"]==8952
 assert receipt["plan_sha256"]==sha(WORK/"edit-plan-v7.json")
 assert receipt["renderer_sha256"]==sha(WORK/"compose_guided_film.py")
 assert sha(render/"CasePath_Guided_Documentary_Silent.mp4")==receipt["video"]["sha256"]
 dest.mkdir(parents=True)
 for name in ["edit-plan-v7.json","compose_guided_film.py","validate_guided_film.py","build_guided_package.py","capture_clean_source_4k.cjs","later-case-date-proof.json","editorial-review.md","score-timeline-final.json","score-guided-final.score.json","film-qa.json","final-visual-qa.log","final-master.log","finish_guided_media.py","publish_guided_evidence.py","README.md","CURRENT_STATE.md","commander-receipts.json","arrow-final.png"]:
  copy(WORK/name,dest/name)
 for name in ["score.py","master_and_mux.py"]:
  copy(ROOT/".runtime/cinema-evidence"/name,dest/name)
 for name in ["CasePath_Guided_Documentary_Silent.mp4","CasePath_Guided_Documentary_Music.mp4","render-receipt.json","full-decode.log","encode.log","decode-source.log"]:
  copy(render/name,dest/name)
 for p in render.glob("CasePath_Guided_Documentary_Music*"):
  if p.is_file() and p.suffix.lower() not in [".mp4",".wav"]:copy(p,dest/p.name)
 for p in render.glob("*mux*.json"):copy(p,dest/p.name)
 archive=[]
 for p in (render/"CasePath_Guided_Documentary_Music-media-evidence").glob("*"):
  if p.is_file() and p.suffix!=".wav":
   target=dest/"media-evidence"/p.name
   if p.suffix==".txt":
    target=target.with_name(target.name+".gz");target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
    archive.append({"original_name":p.name,"original_bytes":p.stat().st_size,"original_sha256":sha(p),"archive":target.name,"archive_sha256":sha(target)})
   else:copy(p,target)
 (dest/"media-evidence"/"archive-manifest.json").write_text(json.dumps({"encoding":"gzip; original log bytes preserved exactly","files":archive},indent=2)+"\n")
 source=WORK/"clean-source-02"
 for name in ["CasePath_Clean_Source.mp4","capture-receipt.json","plates-receipt.json","timeline.json","frame-index.jsonl"]:
  copy(source/name,dest/"clean-source-02"/name)
 plates=sorted({s[k] for s in plan["shots"] for k in ["plate_path","transition_plate_path"] if s.get(k)})
 for name in plates:copy(WORK/name,dest/name)
 for p in sorted(render.glob("contact-*.jpg")):copy(p,dest/"review"/p.name)
 for name in ["shot-001.png","shot-009.png","shot-013.png","shot-015b.png","shot-026.png","shot-034.png","shot-039.png","shot-045.png","shot-052b.png","shot-055.png","shot-061.png","shot-068.png"]:
  copy(render/"frames"/name,dest/"review"/name)
 for p in sorted((WORK/"temporal-qa").glob("*.jpg")):copy(p,dest/"review"/p.name)
 manifest={"contract":"casepath.guided-documentary-package/1","created_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"source_commit":EXPECTED_SOURCE,"frames":plan["frames"],"seconds":plan["duration_seconds"],"files":[]}
 for p in sorted(dest.rglob("*")):
  if p.is_file():
   if p.stat().st_size>=95_000_000:raise ValueError("Git-size guard: "+str(p))
   manifest["files"].append({"path":str(p.relative_to(dest)),"bytes":p.stat().st_size,"sha256":sha(p)})
 (dest/"package-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
 print(json.dumps({"status":"passed","directory":str(dest),"files":len(manifest["files"])+1,"bytes":sum(x["bytes"] for x in manifest["files"]),"manifest_sha256":sha(dest/"package-manifest.json")}))
if __name__=="__main__":main()
