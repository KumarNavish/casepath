#!/usr/bin/env python3
"""Media-only renderer for actual Ego CDP JPEG frames + capture timestamps."""
import argparse,bisect,collections,hashlib,json,math,os,subprocess,sys,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
W,H,FPS=1920,1080,30
COMMIT='7904c8050a10568d4168c92b77ee55ec1d7b2b13'
CLAIM='clm_314f2d309fea25e6'
BG=(239,242,236);INK=(24,61,51)
FONT='/workspace/casepath-release-ae0-inventory/casepath/assets/fonts/OpenSans-VariableFont_wdth-wght.ttf'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(v):
 v=float(v)
 return v/1000 if v>1e11 else v
def rect(v):
 if isinstance(v,list):v=next((x for x in v if isinstance(x,dict)),None)
 if not isinstance(v,dict):return None
 x,y=float(v.get('x',v.get('left',0))),float(v.get('y',v.get('top',0)))
 w,h=float(v.get('width',v.get('w',0))),float(v.get('height',v.get('h',0)))
 return (x,y,w,h) if w>0 and h>0 else None
def overlap(a,b):return a[0]<=b[1] and b[0]<=a[1]
def merge(windows,start,end):
 out=[]
 for a,b in sorted((max(start,a),min(end,b)) for a,b in windows if b>start and a<end):
  if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
  else:out.append([a,b])
 return out
class Movie:
 def __init__(self,args):
  self.args=args;self.root=args.input.parent;self.raw=json.loads(args.input.read_text());self.frames=sorted(self.raw['frames'],key=lambda f:stamp(f['t']));self.samples=sorted(self.raw.get('samples',[]),key=lambda f:stamp(f['t']));self.events=sorted(self.raw.get('events',[]),key=lambda f:stamp(f['t']))
  assert 2<=len(self.frames)<=10000 and self.samples,'Actual frames and timestamped samples required'
  self.ft=[stamp(f['t']) for f in self.frames];self.st=[stamp(s['t']) for s in self.samples];self.et=[stamp(e['t']) for e in self.events]
  self.source_commit=self.raw.get('source_commit',self.raw.get('sourceCommit',args.source_commit));assert self.source_commit==COMMIT,'Wrong source identity'
  assert self.raw.get('claim_id',CLAIM)==CLAIM,'Wrong claim'
  self.paths=[];self.frame_manifest=[]
  for f,t in zip(self.frames,self.ft):
   p=(self.root/f['file']).resolve();assert p.is_relative_to(self.root.resolve()) and p.is_file() and not p.is_symlink();self.paths.append(p)
   self.frame_manifest.append({'file':f['file'],'t':t,'bytes':p.stat().st_size,'sha256':sha(p)})
  assert sum(x['bytes'] for x in self.frame_manifest)<=1536*1024**2,'Raw input exceeds bounded1.5GiB'
  with Image.open(self.paths[0]) as im:self.iw,self.ih=im.size
  v=self.raw.get('viewport') or self.raw.get('css_viewport')
  if args.css_size:self.cw,self.ch=map(int,args.css_size.lower().split('x'))
  elif v:self.cw,self.ch=int(v['width']),int(v['height'])
  else:raise ValueError('Need capture index viewport:{width,height} or --css-size; never guess CSS-to-image coordinates')
  assert min(self.cw,self.ch)>0
  self.sx,self.sy=self.iw/self.cw,self.ih/self.ch;self.cache=collections.OrderedDict();self.caption_font=ImageFont.truetype(FONT,31);self.title_font=ImageFont.truetype(FONT,58);self.sub_font=ImageFont.truetype(FONT,29)
  self.start,self.end=self.ft[0],max(self.ft[-1],max((stamp(e['t']) for e in self.events if e.get('type')=='film-end'),default=self.ft[-1]));self.windows=[];self.labels=[];self.build_plan()
 def sample(self,t):return self.samples[max(0,bisect.bisect_right(self.st,t)-1)]
 def event_text(self,e):return ' '.join(str(e.get(k,'')) for k in ['type','target','selector','reason','label','role']).lower()
 def build_plan(self):
  spans=[];seen_sources=set();prior_check=0;final=None
  # Only genuine captured focus/handoffs/check changes define protected realtime windows.
  for i,s in enumerate(self.samples):
   t=self.st[i];next_t=self.st[i+1] if i+1<len(self.st) else self.end
   if rect(s.get('factRect')):
    spans.append((t-.20,min(next_t,t+.35)+.3));self.labels.append((t-.2,next_t+.35,'Connect the fact'))
   if rect(s.get('readheadRect')):
    text=str(s.get('sourceText',''));identity=s.get('source_id') or s.get('sourceTitle') or hashlib.sha256(text.encode()).hexdigest()
    if identity not in seen_sources:
     seen_sources.add(identity);spans.append((t-.2,t+1.9));self.labels.append((t,t+1.9,'Read the evidence'))
   checked=s.get('checkedSlots',0);checked=len(checked) if isinstance(checked,list) else int(checked or 0)
   if checked>prior_check:spans.append((t-1.1,t+1.5));self.labels.append((t-.7,t+1.5,'Check each document'))
   prior_check=checked
   state=s.get('state');completed=(str(state).lower() in ['completed','complete'] or s.get('verified') is True or s.get('result_verified') is True)
   if completed and final is None:final=t
  # Retain the actual one source-inspection pause and close/resume, never a manufactured hold.
  inspection_start=None
  for e in self.events:
   t=stamp(e['t']);text=self.event_text(e)
   if ('source' in text or 'inspect' in text) and 'close' not in text:
    inspection_start=t;spans.append((t-.35,t+2.0));self.labels.append((t-.2,t+2,'Inspect the source'))
   if 'resume' in text:
    if inspection_start is not None:spans.append((inspection_start-.35,t+1.1))
    self.labels.append((t,t+1.2,'Resume the check'))
  # Start near the genuine first source/rail. Do not waste film duration on a cold blank tab.
  first=next((t for t,s in zip(self.st,self.samples) if rect(s.get('railRect')) and rect(s.get('sourceRect'))),self.start)
  self.start=max(self.start,first-.8)
  if final is not None:self.end=min(self.end,final+5.0)
  spans.extend([(self.start,self.start+2.2),(self.end-5.0,self.end)])
  self.labels.append((self.end-5.0,self.end,'Reach a decision'))
  self.windows=merge(spans,self.start,self.end)
  self.total_target=float(self.args.duration);self.endcard=5.0;self.final_freeze=2.5;target=self.total_target-self.endcard-self.final_freeze
  if target<=0:raise ValueError('duration must include a5s endcard')
  self.dt=.025;self.grid=[self.start+i*self.dt for i in range(int((self.end-self.start)/self.dt)+1)]
  if self.grid[-1]<self.end:self.grid.append(self.end)
  def protection(t):
   distance=min((0 if a<=t<=b else a-t if t<a else t-b) for a,b in self.windows)
   q=max(0,min(1,distance/.4));return q*q*(3-2*q)
  ramp=[protection((a+b)/2) for a,b in zip(self.grid,self.grid[1:])]
  def integrate(speed):
   times=[0.]
   for i,(a,b) in enumerate(zip(self.grid,self.grid[1:])):times.append(times[-1]+(b-a)/(1+(speed-1)*ramp[i]))
   return times
  lo,hi=1.,6.
  minimum=integrate(hi)[-1];maximum=integrate(lo)[-1]
  if target<minimum-.2:raise ValueError(f'Realtime consequential windows require at least{minimum+5+self.final_freeze:.2f}s; do not silently accelerate them')
  if target>maximum:target=maximum
  for _ in range(48):
   mid=(lo+hi)/2
   if integrate(mid)[-1]>target:lo=mid
   else:hi=mid
  self.routine_speed=(lo+hi)/2;self.out_times=integrate(self.routine_speed);self.ui_duration=self.out_times[-1];self.duration=self.ui_duration+self.final_freeze+self.endcard
  assert 45<=self.duration<=75,'Authorized45–75s film limit'
 def input_time(self,t):
  i=max(0,min(len(self.out_times)-2,bisect.bisect_right(self.out_times,t)-1));a,b=self.out_times[i:i+2];q=0 if b==a else (t-a)/(b-a);return self.grid[i]+q*(self.grid[i+1]-self.grid[i])
 def frame(self,t):
  i=max(0,min(len(self.paths)-1,bisect.bisect_right(self.ft,t)-1))
  if i not in self.cache:
   with Image.open(self.paths[i]) as im:
    if im.size!=(self.iw,self.ih):raise ValueError('Capture viewport changed within the film')
    self.cache[i]=im.convert('RGB')
   while len(self.cache)>8:self.cache.popitem(last=False)
  self.cache.move_to_end(i);return self.cache[i]
 def camera(self,t):
  s=self.sample(t);point=rect(s.get('factRect')) or rect(s.get('readheadRect'));zoom=1.085 if point else 1.
  cx,cy=self.iw/2,self.ih/2
  if point:cx=(point[0]+point[2]/2)*self.sx*.2+self.iw*.4;cy=(point[1]+point[3]/2)*self.sy*.12+self.ih*.44
  return cx,cy,zoom
 def keep_destinations(self,t,camera):
  s=self.sample(t);cx,cy,z=camera
  # Real source/rail bounds constrain the editorial crop; never erase a landing slot.
  if s.get('dialog') or s.get('state')=='paused' or any(abs(stamp(e['t'])-t)<.9 for e in self.events if e.get('type')=='click'):return self.iw/2,self.ih/2,1.
  rr=[rect(s.get(k)) for k in ['sourceRect','railRect']];rr=[r for r in rr if r]
  if rr:
   pad=12;left=max(0,min(r[0] for r in rr)-pad)*self.sx;right=min(self.cw,max(r[0]+r[2] for r in rr)+pad)*self.sx;top=max(0,min(r[1] for r in rr)-pad)*self.sy;bottom=min(self.ch,max(r[1]+r[3] for r in rr)+pad)*self.sy
   z=min(z,self.iw/(right-left),self.ih/(bottom-top));cw,ch=self.iw/z,self.ih/z
   cx=max(max(cw/2,right-cw/2),min(min(self.iw-cw/2,left+cw/2),cx));cy=max(max(ch/2,bottom-ch/2),min(min(self.ih-ch/2,top+ch/2),cy))
  return cx,cy,z
 def caption(self,t):
  active=[label for a,b,label in self.labels if a<=t<=b]
  if active:return active[-1]
  return ''
 def cursor(self,t):
  i=bisect.bisect_right(self.et,t)-1
  for e in reversed(self.events[:i+1]):
   if isinstance(e.get('x'),(int,float)) and isinstance(e.get('y'),(int,float)):return float(e['x'])*self.sx,float(e['y'])*self.sy
  return None
 def render_frame(self,out_t,camera=None):
  im=Image.new('RGB',(W,H),BG);draw=ImageDraw.Draw(im)
  if out_t>=self.ui_duration+self.final_freeze:
   for text,y,font in [('CasePath · Evidence into action',446,self.title_font),('Synthetic claims · recorded replay',540,self.sub_font)]:draw.text((W/2,y),text,font=font,fill=INK,anchor='mt')
   return im
  t=self.input_time(min(out_t,self.ui_duration));src=self.frame(t);cx,cy,z=self.keep_destinations(t,camera or self.camera(t));crop_w=self.iw/z;crop_h=self.ih/z;x=max(0,min(self.iw-crop_w,cx-crop_w/2));y=max(0,min(self.ih-crop_h,cy-crop_h/2));box=(x,y,x+crop_w,y+crop_h)
  # Real screenshot pixels only. Reserved caption matte never covers product content.
  maxw,maxh=1856,984;scale=min(maxw/crop_w,maxh/crop_h);ow,oh=round(crop_w*scale),round(crop_h*scale);left=(W-ow)//2;top=14+(984-oh)//2
  content=src.resize((ow,oh),Image.Resampling.LANCZOS,box=box);im.paste(content,(left,top))
  cursor=self.cursor(t)
  if cursor and not self.args.no_cursor:
   px=left+(cursor[0]-x)*scale;py=top+(cursor[1]-y)*scale
   if left<=px<=left+ow and top<=py<=top+oh:
    poly=[(0,0),(0,25),(7,18),(12,29),(17,27),(12,16),(22,16)];pts=[(px+a,py+b) for a,b in poly];draw.polygon(pts,fill=(250,250,248),outline=(25,32,29),width=2)
  cap=self.caption(t)
  if cap:draw.text((W/2,1027),cap,font=self.caption_font,fill=INK,anchor='mm')
  return im
 def contact(self,path):
  # Genuine semantic moments, selected from captured geometry, not uniform guesses.
  picks=[];read=set();flight=set();prior=0;firstcheck=None;inspect=None
  for t,s in zip(self.st,self.samples):
   title=s.get('sourceTitle')
   if title and title not in read and rect(s.get('readheadRect')):read.add(title);picks.append(t+.25)
   if title and title not in flight and rect(s.get('factRect')):flight.add(title);picks.append(t+.18)
   checked=s.get('checkedSlots',0);checked=len(checked) if isinstance(checked,list) else int(checked or 0)
   if checked>prior and firstcheck is None:firstcheck=t+.35
   prior=checked
   if s.get('dialog') and inspect is None:inspect=t+.75
  if inspect is not None:picks.append(inspect)
  if firstcheck is not None:picks.append(firstcheck)
  picks.append(self.end-.2);picks=sorted(picks)[:8]+[self.end-.1] if len(picks)>9 else sorted(picks)
  while len(picks)<9:picks.append(self.start+(self.end-self.start)*(len(picks)+.5)/9);picks.sort()
  sheet=Image.new('RGB',(1920,1080),BG);moments=[]
  for i,t in enumerate(picks[:9]):
   k=max(0,min(len(self.grid)-2,bisect.bisect_right(self.grid,t)-1));a,b=self.grid[k:k+2];q=0 if b==a else (t-a)/(b-a);ot=self.out_times[k]+q*(self.out_times[k+1]-self.out_times[k]);ot=max(0,min(self.ui_duration-.05,ot));sheet.paste(self.render_frame(ot).resize((640,360),Image.Resampling.LANCZOS),((i%3)*640,(i//3)*360));moments.append({'tile':i+1,'source_t':t,'film_t':ot})
  sheet.save(path);(path.parent/'contact-moments.json').write_text(json.dumps(moments,indent=2)+'\n')
 def receipt(self):
  return {'source_commit':self.source_commit,'claim_id':CLAIM,'source_basis':'Mac-owned capture of actual public UI; Cloud network denial prevents independent Cloud live fetch. Source identity is bound to supplied capture receipt.','input_index_sha256':sha(self.args.input),'input_frames':len(self.frames),'input_manifest_sha256':hashlib.sha256(json.dumps(self.frame_manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'native_image_size':[self.iw,self.ih],'css_viewport':[self.cw,self.ch],'output_size':[W,H],'output_fps':FPS,'source_range':[self.start,self.end],'duration_seconds':self.duration,'ui_duration_seconds':self.ui_duration,'endcard_seconds':5,'editorial_final_image_hold_seconds':self.final_freeze,'final_native_frame_t':self.ft[-1],'actual_capture_end_t':self.end,'routine_speed':self.routine_speed,'realtime_windows':self.windows,'captions':self.labels,'camera':'Small eased camera motion from actual recorded head/fact rectangles; the complete actual source/rail bounds constrain every crop. Full UI during native clicks/inspection. No actor reconstruction or frame interpolation.','cursor':'Neutral editorial pointer from actual logged x/y events only; no invented inputs.','audio':False,'endcard':['CasePath · Evidence into action','Synthetic claims · recorded replay'],'limits':['Timeline protection derives from supplied samples/events; inspect contact sheet and EDL before final encoding.','CDP frames are variable-rate;30fps output uses actual preceding captured frames, never invented intermediate UI motion.','The final2.5s is an editorial hold of the actual last decision image, not added engine work.']}
def main():
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--css-size');p.add_argument('--duration',type=float,default=65);p.add_argument('--source-commit',default=COMMIT);p.add_argument('--plan-only',action='store_true');p.add_argument('--no-cursor',action='store_true');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True);movie=Movie(args);receipt=movie.receipt();(args.output/'edit-plan.json').write_text(json.dumps(receipt,indent=2)+'\n');movie.contact(args.output/'contact-sheet-agentic-v4.png')
 print(json.dumps({'status':'PLAN_READY','duration':movie.duration,'routine_speed':movie.routine_speed,'realtime_windows':len(movie.windows)}),flush=True)
 if args.plan_only:return
 out=args.output/'CasePath-demo-agentic-v4.mp4';cmd=['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','medium','-crf','19','-threads','3','-pix_fmt','yuv420p','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart',str(out)];receipt['encode_command']=cmd
 cx,cy,z=movie.camera(movie.start);started=time.time()
 with (args.output/'encode.log').open('w') as log:
  proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
  try:
   for n in range(math.ceil(movie.duration*FPS)):
    t=n/FPS
    if t<movie.ui_duration:
     tx,ty,tz=movie.camera(movie.input_time(t));q=1-math.exp(-6/FPS);cx+=q*(tx-cx);cy+=q*(ty-cy);z+=q*(tz-z)
    frame=movie.render_frame(t,(cx,cy,z));proc.stdin.write(frame.tobytes())
   proc.stdin.close();rc=proc.wait(timeout=180)
   if rc:raise RuntimeError(f'ffmpeg exit{rc}')
  except BaseException:
   proc.kill();proc.wait();raise
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(out)]));videos=[s for s in probe['streams'] if s['codec_type']=='video'];assert len(videos)==1 and not any(s['codec_type']=='audio' for s in probe['streams']);v=videos[0];assert (v['width'],v['height'],v['codec_name'],v['r_frame_rate'])==(1920,1080,'h264','30/1');assert 45<=float(probe['format']['duration'])<=75 and out.stat().st_size<100_000_000
 receipt.update(encoding_seconds=time.time()-started,output_sha256=sha(out),output_bytes=out.stat().st_size,contact_sheet_sha256=sha(args.output/'contact-sheet-agentic-v4.png'),ffprobe=probe,status='ENCODED_FROM_ACTUAL_CAPTURE');(args.output/'edit-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'status':receipt['status'],'sha256':receipt['output_sha256'],'bytes':receipt['output_bytes']}))
if __name__=='__main__':main()
