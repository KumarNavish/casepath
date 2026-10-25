#!/usr/bin/env python3
"""Deterministic editorial compositor. All product pixels come from verified recorded UI."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import argparse, subprocess, hashlib, json, math, collections, sys, time, os
ROOT=Path(os.environ.get("CASEPATH_PRODUCT_ROOT","/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024"))
WORK=Path(os.environ.get("CASEPATH_FILM_WORK",str(ROOT/".runtime/guided-film-20261025")))
FFMPEG=os.environ.get("CASEPATH_FFMPEG","/Users/kumar0002/.local/bin/ffmpeg")
FFPROBE=os.environ.get("CASEPATH_FFPROBE","/Users/kumar0002/.local/bin/ffprobe")
W,H,FPS=1920,1080,30
SRC_W,SRC_H=1920,1080
INK=(22,24,28); MUTED=(83,86,94); CRIMSON=(130,7,42); LINE=(226,226,231)
STAGE=(60,306,1800,716)
FONTPATH=ROOT/"casepath/assets/fonts/Mulish.ttf"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ease(t):
 t=max(0,min(1,t)); return t*t*(3-2*t)
FONT={}
def font(size,weight=450):
 k=(size,weight)
 if k not in FONT:
  f=ImageFont.truetype(str(FONTPATH),int(size))
  try:
   axes=f.get_variation_axes(); vals=[a["default"] for a in axes]
   for i,a in enumerate(axes):
    if b"Weight" in a["name"]: vals[i]=max(a["minimum"],min(a["maximum"],weight))
   f.set_variation_by_axes(vals)
  except (OSError,AttributeError): pass
  FONT[k]=f
 return FONT[k]
MEASURE=ImageDraw.Draw(Image.new("RGB",(1,1)))
def wrap(text,f,maxwidth):
 lines=[];cur=""
 for word in text.split():
  test=(cur+" "+word).strip()
  if cur and MEASURE.textlength(test,font=f)>maxwidth: lines.append(cur);cur=word
  else:cur=test
 if cur:lines.append(cur)
 return lines
def txt(draw,xy,text,size=32,color=INK,weight=450,maxwidth=None,spacing=1.18):
 f=font(size,weight); lines=wrap(text,f,maxwidth) if maxwidth else [text]
 x,y=xy
 for line in lines:draw.text((x,y),line,font=f,fill=color,anchor="lt");y+=round(size*spacing)
 return (x,xy[1],max((MEASURE.textlength(line,font=f) for line in lines),default=0),y-xy[1])
def interpolate(a,b,u): return [aa+(bb-aa)*u for aa,bb in zip(a,b)]
def round_rect(draw,box,fill=None,outline=None,width=1,r=16):
 draw.rounded_rectangle(tuple(int(round(v)) for v in box),radius=r,fill=fill,outline=outline,width=width)
def arrow(draw,start,end,color=CRIMSON,width=3,progress=1):
 ax,ay=start;bx,by=end;tx=ax+(bx-ax)*progress;ty=ay+(by-ay)*progress
 draw.line((ax,ay,tx,ty),fill=color,width=width)
 if progress>.95:
  angle=math.atan2(by-ay,bx-ax); l=14
  pts=[(bx,by),(bx-l*math.cos(angle-.45),by-l*math.sin(angle-.45)),(bx-l*math.cos(angle+.45),by-l*math.sin(angle+.45))]
  draw.polygon(pts,fill=color)
def polyarrow(draw,points,progress,color=CRIMSON,width=3):
 lengths=[math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(points,points[1:])]
 remaining=sum(lengths)*max(0,min(1,progress));shown=[points[0]]
 for i,length in enumerate(lengths):
  a,b=points[i],points[i+1]
  if remaining>=length:shown.append(b);remaining-=length
  else:
   ratio=remaining/length if length else 0;shown.append((a[0]+(b[0]-a[0])*ratio,a[1]+(b[1]-a[1])*ratio));break
 if len(shown)>1:draw.line(shown,fill=color,width=width,joint="curve")
 if progress>=.995:arrow(draw,points[-2],points[-1],color=color,width=width,progress=1)
def source_frame(video,n,cache):
 if n in cache:return cache[n].copy()
 proc=subprocess.run([FFMPEG,"-v","error","-ss",f"{n/FPS:.9f}","-i",str(video),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","pipe:1"],capture_output=True,check=True)
 if len(proc.stdout)!=SRC_W*SRC_H*3:raise ValueError("Bad source decode")
 im=Image.frombytes("RGB",(SRC_W,SRC_H),proc.stdout)
 cache[n]=im
 return im.copy()
class Stream:
 def __init__(self,video,log):
  self.log=open(log,"xb")
  self.proc=subprocess.Popen([FFMPEG,"-nostdin","-v","warning","-i",str(video),"-f","rawvideo","-pix_fmt","rgb24","pipe:1"],stdout=subprocess.PIPE,stderr=self.log)
  self.n=-1;self.cache=collections.OrderedDict()
 def get(self,n):
  if n in self.cache:return self.cache[n]
  if n<self.n:raise ValueError(f"Source clock moved backwards {self.n} -> {n}")
  while self.n<n:
   b=self.proc.stdout.read(SRC_W*SRC_H*3)
   if len(b)!=SRC_W*SRC_H*3:raise ValueError(f"Source decode ended at {self.n}")
   self.n+=1;self.cache[self.n]=Image.frombytes("RGB",(SRC_W,SRC_H),b)
   while len(self.cache)>3:self.cache.popitem(last=False)
  return self.cache[n]
 def close(self):
  if self.proc.poll() is None:self.proc.terminate()
  self.proc.wait(timeout=10);self.log.close()
def project(rect,crop,target):
 x,y,w,h=crop;tx,ty,tw,th=target
 scale=min(tw/w,th/h);ox=tx+(tw-w*scale)/2;oy=ty+(th-h*scale)/2
 rx,ry,rw,rh=rect
 return (ox+(rx-x)*scale,oy+(ry-y)*scale,rw*scale,rh*scale)
def place_source(im,crop):
 x,y,w,h=crop
 if w<=0 or h<=0:raise ValueError("Empty camera")
 tx,ty,tw,th=STAGE;sc=min(tw/w,th/h);rw=max(1,round(w*sc));rh=max(1,round(h*sc))
 factor=im.width/W
 pic=im.crop((round(x*factor),round(y*factor),round((x+w)*factor),round((y+h)*factor))).resize((rw,rh),Image.Resampling.LANCZOS)
 stage=Image.new("RGB",(tw,th),"white");stage.paste(pic,((tw-rw)//2,(th-rh)//2))
 return stage
def header(canvas,shot,local,total_frame,total_frames,same_copy=False):
 d=ImageDraw.Draw(canvas)
 txt(d,(61,33),"CasePath",29,INK,650)
 if shot.get("case_badge"):txt(d,(270,40),shot["case_badge"],20,MUTED,600)
 # Upper-right chapter context has a stable place throughout.
 text=shot["chapter"];f=font(22,600);width=MEASURE.textlength(text,font=f)
 d.text((1858-width,39),text,font=f,fill=CRIMSON,anchor="lt")
 d.line((60,82,1860,82),fill=LINE,width=1)
 layer=Image.new("RGBA",(W,H),(0,0,0,0));q=ImageDraw.Draw(layer)
 delay=0 if same_copy else .30
 fade=1 if same_copy else ease((local-delay)/.55)
 y=111+round(10*(1-fade))
 title="" if shot.get("layout")=="hero" else shot["title"];f=font(55,650);lines=wrap(title,f,1795)
 if len(lines)>2:raise ValueError("Title exceeds 2 lines: "+shot["id"])
 for line in lines:q.text((61,y),line,font=f,fill=INK+(255,),anchor="lt");y+=65
 if shot.get("subtitle") and shot.get("layout")!="hero":
  sf=font(30,450);sl=wrap(shot["subtitle"],sf,1770)
  if len(sl)>1:raise ValueError("Subtitle exceeds 1 line: "+shot["id"])
  q.text((63,y+13),sl[0],font=sf,fill=MUTED+(255,),anchor="lt")
 if fade<1:layer.putalpha(layer.getchannel("A").point(lambda a:int(a*fade)))
 canvas.paste(layer,(0,0),layer)
 d=ImageDraw.Draw(canvas)
 txt(d,(61,1043),"Recorded demonstration · Fictional cases · Human review required",19,MUTED,450)
 txt(d,(1647,1043),"CASEPATH / FILM",18,MUTED,600)
 d.line((60,1072,1860,1072),fill=LINE,width=3)
 d.line((60,1072,60+int(1800*(total_frame+1)/total_frames),1072),fill=CRIMSON,width=3)
def hero(canvas,shot,local):
 d=ImageDraw.Draw(canvas)
 txt(d,(135,337),shot.get("hero_kicker",""),20,CRIMSON,650)
 txt(d,(131,401),"Is this rent increase notice valid?",83,INK,650,maxwidth=1370,spacing=1.15)
 d.line((135,648,290,648),fill=CRIMSON,width=4)
 txt(d,(135,692),shot.get("hero_note",""),34,MUTED,450,maxwidth=1500)
 # Simple evidence-page symbol, editorial only, no invented UI or data.
 x,y=1660,382
 d.rounded_rectangle((x-38,y+24,x+112,y+227),radius=8,fill=(246,241,243),outline=(229,210,216),width=2)
 d.rounded_rectangle((x-15,y+10,x+135,y+213),radius=8,fill="white",outline=(192,165,174),width=2)
 d.rounded_rectangle((x+10,y-4,x+160,y+199),radius=8,fill="white",outline=CRIMSON,width=3)
 for i,l in enumerate([100,95,107,68]):d.line((x+32,y+47+i*26,x+32+l,y+47+i*26),fill=LINE,width=4)
def journey(canvas,shot,local):
 local+=shot.get("visual_offset_s",0)
 d=ImageDraw.Draw(canvas);nodes=shot["nodes"];x0=95;gap=50;cw=395;y=468;ch=176
 labels=["Original records","Case-specific requirements","Scoped reasoning","A person decides"]
 active=min(3,int(max(0,local-.4)/1.15))
 for i,name in enumerate(nodes):
  x=x0+i*(cw+gap);progress=ease((local-.30-i*.25)/.6)
  color=CRIMSON if i<=active else (175,176,183)
  round_rect(d,(x,y,x+cw,y+ch),fill=(255,255,255),outline=color,width=2,r=15)
  txt(d,(x+28,y+28),f"0{i+1}",19,color,650)
  txt(d,(x+28,y+66),name,32,INK,650,maxwidth=cw-50,spacing=1.18)
  if i<3:arrow(d,(x+cw+10,y+ch/2),(x+cw+gap-10,y+ch/2),color=CRIMSON if i<active else LINE,width=2,progress=progress)
def chronology(canvas,shot,local):
 d=ImageDraw.Draw(canvas)
 for i,node in enumerate(shot["date_nodes"]):
  x=170+i*850;y=420;cw=730;ch=255
  fade=ease((local-(1.0+i*1.2))/.65)
  layer=Image.new("RGBA",(W,H),(0,0,0,0));q=ImageDraw.Draw(layer)
  round_rect(q,(x,y,x+cw,y+ch),fill=(255,255,255,255),outline=CRIMSON+(255,),width=2,r=18)
  txt(q,(x+42,y+44),node["date"],49,CRIMSON+(255,),650)
  txt(q,(x+42,y+129),node["label"],38,INK+(255,),600)
  layer.putalpha(layer.getchannel("A").point(lambda a:int(a*fade)))
  canvas.paste(layer,(0,0),layer)
 d=ImageDraw.Draw(canvas)
 if local>2.5:arrow(d,(921,548),(998,548),width=3,progress=ease((local-2.5)/1.0))
 txt(d,(173,748),shot["source_caption"],26,MUTED,450,maxwidth=1560)
def render(im,shot,local,total_frame,total_frames,prev_crop=None,prev_shot=None):
 canvas=Image.new("RGB",(W,H),"white")
 layout=shot.get("layout","source")
 if layout=="hero":hero(canvas,shot,local)
 elif layout=="journey":journey(canvas,shot,local)
 elif layout=="chronology":chronology(canvas,shot,local)
 else:
  crop=shot["crop"]
  if prev_crop is not None and not shot.get("bridge"):
   crop=interpolate(prev_crop,crop,ease(local/1.05))
  stage=place_source(im,crop);base=stage.copy()
  tx,ty,tw,th=STAGE
  focus=shot.get("focus",[])
  if shot.get("focus_by_source"):
   source_ms=(shot["source_frame"]/FPS+local)*1000
   for cue in shot["focus_by_source"]:
    if cue["start_ms"]<=source_ms<cue["end_ms"]:focus=[cue["rect"]];break
  if focus or shot.get("bridge"):
   dim=.24 if focus else .13
   stage=Image.blend(base,Image.new("RGB",base.size,(106,108,117)),dim)
   if focus:
    mask=Image.new("L",stage.size,0);md=ImageDraw.Draw(mask)
    for r in focus:
     x,y,w,h=project(r,crop,STAGE);round_rect(md,(x-tx-8,y-ty-8,x-tx+w+8,y-ty+h+8),fill=255,r=10)
    mask=mask.filter(ImageFilter.GaussianBlur(1.2));stage.paste(base,(0,0),mask)
  canvas.paste(stage,(tx,ty))
  d=ImageDraw.Draw(canvas)
  round_rect(d,(tx,ty,tx+tw,ty+th),outline=LINE,width=1,r=17)
  opacity=ease((local-(.15 if shot.get("focus_by_source") else 1.0))/.35)
  if focus and opacity>0:
   overlay=Image.new("RGBA",(W,H),(0,0,0,0));od=ImageDraw.Draw(overlay)
   boxes=[]
   for r in focus:
    x,y,w,h=project(r,crop,STAGE)
    a=max(tx+2,x-8);b=max(ty+2,y-8);c=min(tx+tw-2,x+w+8);e=min(ty+th-2,y+h+8)
    if c<=a or e<=b:
     if local>=1.05:raise ValueError("Focus outside camera: "+shot["id"])
     continue
    round_rect(od,(a,b,c,e),outline=CRIMSON+(int(opacity*235),),width=3,r=12);boxes.append((a,b,c,e))
   if shot.get("label") and boxes:
    a,b,c,e=boxes[0];label=shot["label"];lf=font(22,650);lw=MEASURE.textlength(label,font=lf)
    lx=64;ly=269
    round_rect(od,(lx-9,ly-5,lx+lw+10,ly+27),fill=(255,255,255,int(opacity*255)),r=4)
    od.text((lx,ly),label,font=lf,fill=CRIMSON+(int(opacity*255),),anchor="lt")
   canvas.paste(overlay,(0,0),overlay)
  if shot.get("connection"):
   (a,b)=shot["connection"];pa=project([a[0],a[1],0,0],crop,STAGE);pb=project([b[0],b[1],0,0],crop,STAGE)
   overlay=Image.new("RGBA",(W,H),(0,0,0,0));od=ImageDraw.Draw(overlay)
   progress=ease((local-2.2)/1.3)
   arrow(od,pa[:2],pb[:2],color=CRIMSON+(220,),width=4,progress=progress)
   canvas.paste(overlay,(0,0),overlay)
  if shot.get("connection_path"):
   points=[project([p[0],p[1],0,0],crop,STAGE)[:2] for p in shot["connection_path"]]
   overlay=Image.new("RGBA",(W,H),(0,0,0,0));od=ImageDraw.Draw(overlay)
   polyarrow(od,points,ease((local-2.0)/1.35),color=CRIMSON+(220,),width=4)
   canvas.paste(overlay,(0,0),overlay)
  if shot.get("flow"):
   # Editorial relationship sits in the lower margin, outside source wording.
   a,b=shot["flow"];f=font(24,600);aw=MEASURE.textlength(a,font=f);bw=MEASURE.textlength(b,font=f)
   total=aw+bw+126;x=960-total/2;y=265
   round_rect(d,(x-20,y-14,x+total+20,y+40),fill=(255,255,255),outline=LINE,width=1,r=9)
   d.text((x,y),a,font=f,fill=CRIMSON,anchor="lt");arrow(d,(x+aw+25,y+11),(x+aw+99,y+11),width=2,progress=ease((local-1.3)/.8))
   d.text((x+aw+126,y),b,font=f,fill=INK,anchor="lt")
 same=bool(prev_shot and (prev_shot["title"],prev_shot.get("subtitle"))==(shot["title"],shot.get("subtitle")))
 header(canvas,shot,local,total_frame,total_frames,same)
 return canvas
def main():
 global SRC_W,SRC_H
 ap=argparse.ArgumentParser();ap.add_argument("--plan",required=True);ap.add_argument("--out",required=True);ap.add_argument("--preview",action="store_true")
 a=ap.parse_args();planpath=Path(a.plan);plan=json.loads(planpath.read_text());out=Path(a.out)
 if out.exists():raise ValueError("Fresh output directory required")
 out.mkdir(parents=True);(out/"frames").mkdir()
 video=WORK/plan["source_film"];cap=json.loads((WORK/plan["source_capture"]).read_text())
 assert cap["status"]=="passed" and cap["source_commit"]==plan["product_source"]
 SRC_W,SRC_H=cap["width"],cap["height"]
 assert (SRC_W,SRC_H) in [(1920,1080),(3840,2160)]
 assert sha(video)==plan["source_film_sha256"]==cap["video"]["sha256"]
 assert plan["fps"]==FPS and plan["width"]==W and plan["height"]==H
 rows=plan["shots"];nxt=0;srcnext=0
 dateproof=json.loads((WORK/"later-case-date-proof.json").read_text())
 assert dateproof["status"]=="passed" and dateproof["claim_id"]=="clm_7dbd7c7d1c4ddf90"
 assert dateproof["dates"]=={"original_notice":"2025-11-22","later_email":"2025-11-25"}
 for shot in rows:
  assert shot["start_frame"]==nxt and shot["end_frame"]-nxt==shot["frames"];nxt=shot["end_frame"]
  if shot["kind"]=="play":assert shot["source_frame"]==srcnext;srcnext+=shot["frames"]
  x,y,w,h=shot["crop"];assert x>=0 and y>=0 and x+w<=W and y+h<=H
 assert nxt==plan["frames"] and srcnext==2957
 receipt={"contract":"casepath.guided-documentary-render/1","started_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"source_commit":plan["product_source"],
 "plan_sha256":sha(planpath),"renderer_sha256":sha(__file__),"font_sha256":sha(FONTPATH),"source_video_sha256":sha(video),
 "source_capture_receipt_sha256":sha(WORK/plan["source_capture"]),"later_case_date_proof_sha256":sha(WORK/"later-case-date-proof.json"),"requires_audio":False,"preview_only":a.preview,"source_raster":[SRC_W,SRC_H],"camera_reference_raster":[W,H],
 "product_source_modified":False,"new_inference":False,"frames":plan["frames"],"duration":plan["duration_seconds"],"source_clock_frames_covered_in_order":srcnext,
 "shots":[], "status":"running"}
 index=0;cache={};plate_cache={};prev_crop=None;prev_shot=None;prev_source=None;enc=None;stream=None;enc_log=None;expected_samples=set(round(i*(nxt-1)/23) for i in range(24))
 def plate(p):
  if p not in plate_cache:
   f=WORK/p
   match=next((q for q in cap["anchors"] if str(f).endswith(q["path"])),None)
   if match is None or sha(f)!=match["sha256"]:raise ValueError("Unbound orientation plate: "+p)
   plate_cache[p]=Image.open(f).convert("RGB")
  return plate_cache[p]
 try:
  if not a.preview:
   stream=Stream(video,out/"decode-source.log");enc_log=open(out/"encode.log","xb")
   enc=subprocess.Popen([FFMPEG,"-nostdin","-hide_banner","-loglevel","warning","-f","rawvideo","-pix_fmt","rgb24","-s:v","1920x1080","-r","30","-i","pipe:0","-frames:v",str(nxt),"-c:v","libx264","-preset","fast","-crf","17","-pix_fmt","yuv420p","-an","-movflags","+faststart",str(out/"CasePath_Guided_Documentary_Silent.mp4")],stdin=subprocess.PIPE,stderr=enc_log)
  for shot in rows:
   mid=shot["frames"]//2
   sample_range=[mid] if a.preview else range(shot["frames"])
   for j in sample_range:
    src=shot["source_frame"]+(j if shot["kind"]=="play" else 0)
    im=source_frame(video,src,cache) if a.preview else stream.get(src)
    if shot.get("plate_path"):im=plate(shot["plate_path"])
    if shot.get("transition_plate_path"):
     new=plate(shot["transition_plate_path"])
     if a.preview:
      prior_src=max(0,shot["source_frame"]-1);prior=source_frame(video,prior_src,cache)
     else:prior=prev_source if prev_source is not None else im
     im=Image.blend(prior,new,ease(j/max(1,shot["frames"]-1)))
    n=shot["start_frame"]+j
    frame=render(im,shot,j/FPS,n,nxt,prev_crop,prev_shot)
    if j==mid or n in expected_samples:
     label=("shot-"+shot["id"]) if j==mid else f"sample-{n:05d}"
     p=out/"frames"/(label+".png");frame.save(p,optimize=False)
     receipt["shots"].append({"shot":shot["id"],"film_frame":n,"film_seconds":n/FPS,"source_frame":src,"source_seconds":src/FPS,"editorial_plate":shot.get("plate_path"),"editorial_plate_ms":shot.get("plate_time_ms"),"transition_plate":shot.get("transition_plate_path"),"transition_plate_ms":shot.get("transition_plate_time_ms"),"path":str(p.relative_to(out)),"sha256":sha(p),"title":shot["title"]})
    if enc:
     enc.stdin.write(frame.tobytes())
     if enc.poll() is not None:raise RuntimeError("Encoder stopped")
   prev_crop=shot["crop"];prev_shot=shot;prev_source=im
   print(json.dumps({"stage":"preview" if a.preview else "render","shot":shot["id"],"of":len(rows),"film_seconds":shot["end_frame"]/FPS}),flush=True)
  if enc:
   enc.stdin.close();code=enc.wait()
   if code:raise RuntimeError("Encoder failed")
   enc_log.close();enc_log=None;stream.close();stream=None
   f=out/"CasePath_Guided_Documentary_Silent.mp4"
   probe=json.loads(subprocess.run([FFPROBE,"-v","error","-show_streams","-show_format","-of","json",str(f)],capture_output=True,text=True,check=True).stdout)
   v=next(s for s in probe["streams"] if s["codec_type"]=="video")
   assert int(v["nb_frames"])==nxt and v["avg_frame_rate"]=="30/1" and v["width"]==W and v["height"]==H
   with (out/"full-decode.log").open("xb") as log:subprocess.run([FFMPEG,"-nostdin","-v","error","-i",str(f),"-f","null","-"],stdout=log,stderr=log,check=True)
   receipt["video"]={"path":f.name,"bytes":f.stat().st_size,"sha256":sha(f),"probe":probe}
  # Contact sheets of actual preview/production frames, grouped for legible review.
  shotrows=[r for r in receipt["shots"] if r["path"].split("/")[-1].startswith("shot-")]
  for g in range(math.ceil(len(shotrows)/12)):
   group=shotrows[g*12:(g+1)*12];sheet=Image.new("RGB",(1920,960),"white");sd=ImageDraw.Draw(sheet)
   for k,r in enumerate(group):
    im=Image.open(out/r["path"]);im.thumbnail((472,266),Image.Resampling.LANCZOS);x=(k%4)*480+4;y=(k//4)*320+4;sheet.paste(im,(x,y))
    txt(sd,(x+3,y+274),f'{r["shot"]} · {r["film_seconds"]:.1f}s',18,CRIMSON,600)
    txt(sd,(x+3,y+298),r["title"],14,INK,450,maxwidth=464)
   sheet.save(out/f"contact-{g+1:02d}.jpg",quality=95)
  receipt["status"]="passed";receipt["finished_at"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
  (out/"render-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
  print(json.dumps({"status":"passed","out":str(out),"preview_only":a.preview,"frames":nxt,"seconds":nxt/FPS,"video":receipt.get("video",{}).get("sha256")}),flush=True)
 except Exception as e:
  receipt["status"]="failed";receipt["error"]=repr(e);(out/"render-failure.json").write_text(json.dumps(receipt,indent=2)+"\n")
  if enc and enc.poll() is None:enc.terminate();enc.wait(timeout=10)
  raise
 finally:
  if stream:stream.close()
  if enc_log:enc_log.close()
if __name__=="__main__":main()
