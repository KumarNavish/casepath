"""Decode 24 evenly spaced frames from the actual finalized public recording."""
if not __debug__: raise RuntimeError("Assertions required")
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, subprocess, struct
NS=Path(__file__).resolve().parent.parent
BASE=NS/"release"
SHA="b20685d1670b33b941b1bfcb902638a879c01b93"
BROWSER=BASE/("published-browser-"+SHA[:8])
OUT=BASE/"public-film-review"
FFMPEG=Path("/Users/kumar0002/Library/Caches/ms-playwright/ffmpeg-1011/ffmpeg-mac")
read=lambda p:json.loads(p.read_text())
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
acceptance=read(BASE/"published-acceptance-sequence.json")
assert acceptance["status"]=="passed" and acceptance["source_commit"]==SHA
report=read(BROWSER/"published-verification.json")
film=report["film"];video=BROWSER/"public-walkthrough.webm"
assert report["expected_commit"]==film["source_commit"]==SHA
assert film["viewport"]=={"width":1440,"height":900}
assert film["reached_end"] and film["duration_ms"]==88050
assert not film["errors"] and not film["writes"]
assert video.is_file() and digest(video)==film["video_sha256"]
assert not OUT.exists()
OUT.mkdir()
receipt={"contract":"casepath.actual-film-cold-review/1","source_commit":SHA,"created_at":datetime.now(timezone.utc).isoformat(),"video":str(video),"video_sha256":digest(video),"video_bytes":video.stat().st_size,"viewport":{"width":1440,"height":900},"playback_clock_observations":{key:film[key] for key in ("recording_requested_at","playback_first_observed_at","playback_observed_end_at","wall_ms","duration_ms")},"exact_video_pts_to_browser_clock_mapping_claimed":False,"synthetic_or_seeked_browser_frames":False,"status":"running","frames":[]}
def persist(): (OUT/"frames-index.json").write_text(json.dumps(receipt,indent=2)+"\n")
persist()
try:
 probe=subprocess.run([str(FFMPEG),"-hide_banner","-i",str(video)],text=True,capture_output=True,timeout=30)
 (OUT/"video-metadata.log").write_text(probe.stderr)
 match=re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)",probe.stderr)
 assert match,"Recorded video duration not available"
 hours,minutes,seconds=map(float,match.groups())
 duration=hours*3600+minutes*60+seconds
 assert duration>=88.05
 assert re.search(r"\b1440x900\b",probe.stderr),"Record viewport was not preserved"
 receipt.update(recorded_duration_seconds=duration,interval={"start_seconds":0,"end_seconds":duration,"scope":"Full continuous finalized recording, including cold load and playback; each frame is decoded at the midpoint of one of 24 equal intervals."})
 persist()
 for i in range(24):
  at=(i+.5)*duration/24
  target=OUT/("cold-frame-%02d.png"%(i+1))
  command=[str(FFMPEG),"-v","error","-ss","%.6f"%at,"-i",str(video),"-frames:v","1",str(target)]
  result=subprocess.run(command,capture_output=True,text=True,timeout=45)
  assert result.returncode==0,result.stderr[-2000:]
  raw=target.read_bytes()
  assert raw[:8]==b"\x89PNG\r\n\x1a\n" and struct.unpack(">II",raw[16:24])==(1440,900)
  receipt["frames"].append({"number":i+1,"at_seconds":round(at,6),"file":target.name,"sha256":digest(target),"bytes":len(raw)})
  persist()
 receipt["status"]="passed";receipt["decoded_frames"]=len(receipt["frames"]);persist()
 print(json.dumps({"status":"passed","source_commit":SHA,"decoded_frames":24,"recorded_duration_seconds":duration,"index":str(OUT/"frames-index.json")}))
except BaseException as error:
 receipt["status"]="failed";receipt["failure"]=repr(error);persist();raise
