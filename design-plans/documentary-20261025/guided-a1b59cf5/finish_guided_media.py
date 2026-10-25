#!/usr/bin/env python3
"""Wait for this render, then run two independent final-media checks."""
from pathlib import Path
import json,subprocess,time,concurrent.futures,sys
R=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024");G=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024/.runtime/guided-film-20261025");O=G/"final-render"
PY=str(R/".runtime/casepath-dev-v2/venv/bin/python")
deadline=time.monotonic()+1800
while not (O/"render-receipt.json").exists():
 if (O/"render-failure.json").exists():raise RuntimeError("Final renderer failed; inspect render-failure.json")
 if time.monotonic()>deadline:raise TimeoutError("Final render did not finish")
 time.sleep(2)
r=json.loads((O/"render-receipt.json").read_text());assert r["status"]=="passed" and not r["preview_only"]
print(json.dumps({"stage":"final_media_checks","frames":r["frames"]}),flush=True)
jobs={
"master":[PY,"-B",str(R/".runtime/cinema-evidence/master_and_mux.py"),"--silent",str(O/"CasePath_Guided_Documentary_Silent.mp4"),"--score",str(G/"score-guided-final.wav"),"--out",str(O/"CasePath_Guided_Documentary_Music.mp4"),"--expected-frames","8952"],
"visual-qa":[PY,"-B",str(G/"validate_guided_film.py")]
}
def run(item):
 name,cmd=item
 with (G/("final-"+name+".log")).open("xb") as log:p=subprocess.run(cmd,stdout=log,stderr=log)
 return {"job":name,"exit_code":p.returncode,"log":"final-"+name+".log"}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:rows=list(ex.map(run,jobs.items()))
print(json.dumps({"stage":"completed","jobs":rows,"passed":all(r["exit_code"]==0 for r in rows)}),flush=True)
sys.exit(0 if all(r["exit_code"]==0 for r in rows) else 1)
