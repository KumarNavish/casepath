#!/usr/bin/env python3
"""Validate the encoded film, its reading clock and targeted temporal sequences."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageChops,ImageStat
import subprocess,json,hashlib,math,time
G=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024/.runtime/guided-film-20261025");R=G/"final-render";OUT=G/"temporal-qa"
FF="/Users/kumar0002/.local/bin/ffmpeg";FP="/Users/kumar0002/.local/bin/ffprobe"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 assert not OUT.exists(),"Fresh QA directory required"
 OUT.mkdir()
 plan=json.loads((G/"edit-plan-v7.json").read_text());r=json.loads((R/"render-receipt.json").read_text())
 film=R/"CasePath_Guided_Documentary_Silent.mp4"
 assert r["status"]=="passed" and not r["preview_only"]
 assert sha(film)==r["video"]["sha256"]
 assert r["plan_sha256"]==sha(G/"edit-plan-v7.json")
 assert r["renderer_sha256"]==sha(G/"compose_guided_film.py")
 assert r["later_case_date_proof_sha256"]==sha(G/"later-case-date-proof.json")
 shots={s["id"]:s for s in plan["shots"]};fps=plan["fps"];rows=[]
 windows=[]
 for s in plan["shots"]:
  key=(s["title"],s.get("subtitle",""))
  if windows and tuple(windows[-1]["copy"])==key:windows[-1]["end_frame"]=s["end_frame"];windows[-1]["shots"].append(s["id"])
  else:windows.append({"copy":list(key),"start_frame":s["start_frame"],"end_frame":s["end_frame"],"shots":[s["id"]]})
 for w in windows:
  w["seconds"]=(w["end_frame"]-w["start_frame"])/fps;w["words"]=len(" ".join(w["copy"]).split());w["words_per_second"]=w["words"]/w["seconds"]
 def frame(n):
  out=OUT/f"encoded-{n:05d}.png"
  if not out.exists():
   subprocess.run([FF,"-nostdin","-v","error","-ss",f"{n/fps:.9f}","-i",str(film),"-frames:v","1",str(out)],check=True,capture_output=True)
  return out
 # Compare the actual decoded middle of every shot to its authored raster.
 errors=[]
 for q in r["shots"]:
  if not Path(q["path"]).name.startswith("shot-"):continue
  got=frame(q["film_frame"]);a=Image.open(got).convert("RGB");b=Image.open(R/q["path"]).convert("RGB")
  diff=ImageStat.Stat(ImageChops.difference(a,b));mae=sum(diff.mean)/3
  assert mae<4.0,(q["shot"],mae)
  errors.append({"shot":q["shot"],"film_frame":q["film_frame"],"mean_absolute_rgb_error":round(mae,6),"encoded_sha256":sha(got)})
 font=ImageFont.truetype("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024/casepath/assets/fonts/Mulish.ttf",20)
 sequences={
  "email-timing":[("015a",0.4),("015a",2.0),("015b",1.2),("015c",2.0)],
  "assessment-focus":[("036",0.8),("036",2.2),("037",2.5),("038",2.5),("038",4.4),("039",3.0)],
  "reuse-connector":[("055",1.4),("055",2.5),("055",3.6),("055",4.5)],
  "three-reused-checks":[("056",0.2),("056",2.9),("056",5.5),("056",8.2),("057",2.0)],
  "closing-continuity":[("067",4.8),("067",5.1),("068",0.0),("068",1.5)],
 }
 seqrows=[]
 for name,cues in sequences.items():
  sheet=Image.new("RGB",(1920,math.ceil(len(cues)/2)*580),"white");d=ImageDraw.Draw(sheet);items=[]
  for i,(sid,t) in enumerate(cues):
   s=shots[sid];j=min(s["frames"]-1,round(t*fps));n=s["start_frame"]+j
   got=frame(n);im=Image.open(got);im.thumbnail((952,536),Image.Resampling.LANCZOS)
   x=4+(i%2)*960;y=4+(i//2)*580;sheet.paste(im,(x,y))
   d.text((x+5,y+544),f"Shot {sid} | film {n/fps:.3f}s | local {j/fps:.3f}s",font=font,fill=(130,7,42))
   items.append({"shot":sid,"film_frame":n,"local_seconds":j/fps,"encoded_sha256":sha(got)})
  dest=OUT/(name+".jpg");sheet.save(dest,quality=95);seqrows.append({"name":name,"contact_sheet":str(dest.relative_to(G)),"sha256":sha(dest),"samples":items})
 report={"contract":"casepath.guided-documentary-qa/1","status":"passed","created_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"source_commit":plan["product_source"],"plan_sha256":sha(G/"edit-plan-v7.json"),"film_sha256":sha(film),"frames":plan["frames"],"seconds":plan["duration_seconds"],"source_raster":r["source_raster"],"export_raster":[1920,1080],"fps":30,"source_clock_coverage":r["source_clock_frames_covered_in_order"],"all_shot_encoded_comparisons":errors,"max_mean_absolute_rgb_error":max(e["mean_absolute_rgb_error"] for e in errors),"reading_windows":windows,"temporal_sequences":seqrows,"visual_review":{"complete_story":"Independent ordered contact-sheet review and selected full-resolution frames, followed by targeted 4K preview review.","encoded_temporal_review":"Pending root inspection of the five encoded sequence contact sheets.","human_study":False,"real_time_human_playback_test":False},"scope":"Film-only edit; no app source modifications, application mutations or new inference."}
 (G/"film-qa.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({"status":"passed","shots_compared":len(errors),"max_mean_absolute_rgb_error":report["max_mean_absolute_rgb_error"],"temporal_sheets":[x["contact_sheet"] for x in seqrows],"reading_windows":len(windows),"max_caption_words_per_second":max(w["words_per_second"] for w in windows)}))
if __name__=="__main__":main()
