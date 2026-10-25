#!/usr/bin/env python3
"""Original restrained CasePath score, aligned to actual presentation acts.

Soft additive keyboard and sustained open voicings. No recordings, network,
APIs or model calls. NumPy is optional; standard-library rendering is supported.
This is synthesized sound, not a recording of a physical felt piano.
"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys
import wave

try:
    import numpy as np
except ImportError:
    np = None

TAU = math.tau


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x*x*(3.0-2.0*x)


def read_timeline(filename):
    value = json.loads(Path(filename).read_text())
    for key in ('timeline','manifest'):
        if isinstance(value,dict) and isinstance(value.get(key),dict):
            value = value[key]
            break
    if not isinstance(value,dict):
        raise ValueError('Expected a presentation timeline object.')
    duration, acts = value.get('duration'), value.get('acts')
    if not isinstance(duration,(int,float)) or duration<=0:
        raise ValueError('Timeline duration must be positive milliseconds.')
    if not isinstance(acts,list) or not acts:
        raise ValueError('Timeline must contain actual act boundaries.')
    clean, previous = [], -1.0
    for act in acts:
        if not isinstance(act,dict):
            raise ValueError('Invalid act record.')
        start,end = act.get('start'),act.get('end')
        if start is None and end is None:
            continue
        if not all(isinstance(t,(int,float)) for t in (start,end)):
            raise ValueError('Invalid act timing.')
        if start<0 or end<=start or start<previous or end>duration+0.01:
            raise ValueError('Act boundaries must be ordered and within the film.')
        clean.append({'id':str(act.get('id','act')),
                      'start':start/1000.0,'end':end/1000.0})
        previous=start
    if not clean:
        raise ValueError('No usable act boundaries.')
    return duration/1000.0,clean


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeline',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--sample-rate',type=int,default=32000)
    parser.add_argument('--duration',type=float,default=None,
                        help='Optional exact encoded-film duration, seconds.')
    parser.add_argument('--peak-dbfs',type=float,default=-7.0)
    args=parser.parse_args()
    if args.sample_rate not in (24000,32000,44100,48000):
        raise ValueError('Use 24000, 32000, 44100 or 48000 Hz.')
    if not -18<=args.peak_dbfs<=-3:
        raise ValueError('Peak target must be between -18 and -3 dBFS.')
    timeline_path=Path(args.timeline).resolve()
    output_path=Path(args.out).resolve()
    receipt_path=output_path.with_suffix('.score.json')
    if output_path.exists() or receipt_path.exists():
        raise FileExistsError('Preserve previous outputs; choose a new filename.')
    film_duration,acts=read_timeline(timeline_path)
    duration=args.duration if args.duration is not None else film_duration
    if duration<film_duration-0.05 or not 5<=duration<=600:
        raise ValueError('Duration must cover the timeline and be 5–600 seconds.')
    rate=args.sample_rate
    samples=int(math.ceil(duration*rate))
    duration=samples/rate
    left=np.zeros(samples,dtype=np.float64) if np is not None else array.array('d',[0.0])*samples
    right=np.zeros(samples,dtype=np.float64) if np is not None else array.array('d',[0.0])*samples
    events=[]

    def add(kind,start,length,note,amplitude,pan=0.0,label=''):
        if start>=duration or length<=0:
            return
        if not 0<=amplitude<=0.25:
            raise ValueError('Unexpected synthesis amplitude.')
        events.append({'kind':kind,'start':max(0.0,start),'length':length,
                       'midi':note,'frequency':440*2**((note-69)/12),
                       'amplitude':amplitude,'pan':max(-0.6,min(0.6,pan)),
                       'label':label})

    chords={'customer':[50,57,62,64],'reading':[47,54,57,62],
            'process':[43,50,57,59],'decision':[45,52,57,62],
            'learning':[43,50,57,59],'cases':[50,57,59,64]}
    motifs={'customer':[62,69,76],'reading':[62,66,69],
            'process':[62,69,71],'decision':[64,69,74],
            'learning':[62,67,69],'cases':[62,69,76]}
    for index,act in enumerate(acts):
        name,start,end=act['id'],act['start'],min(duration,act['end'])
        length=end-start
        chord=chords.get(name,[50,57,62,64])
        motif=motifs.get(name,[62,69,76])
        pad_start=max(0.0,start-1.25)
        pad_end=min(duration,end+2.25)
        build=0.88+0.18*index/max(1,len(acts)-1)
        for voice,note in enumerate(chord):
            add('pad',pad_start,pad_end-pad_start,note,
                0.0105*build*(0.86 if voice==0 else 1),
                [-0.32,0.24,-0.12,0.35][voice],name+': open voicing')
        for j,(note,offset) in enumerate(zip(motif,[0.90,2.15,3.65])):
            if offset+1<length:
                add('key',start+offset,6.5,note,[0.073,0.060,0.057][j]*build,
                    [-0.18,0.12,0.25][j],name+': chapter motif')
        if length>6:
            add('key',start+1.05,7.5,chord[0],0.038*build,-0.06,
                name+': quiet foundation')
        if length>18:
            add('key',start+length*0.52,6,chord[2]+12,0.043*build,0.17,
                name+': sustained attention')
        if length>30:
            add('key',start+length*0.76,6,chord[1]+12,0.038*build,-0.17,
                name+': sustained attention')
    last=acts[-1]
    if last['end']-last['start']>13:
        closing=max(last['start']+6,duration-10)
        for offset,note,level in ((0,62,0.054),(1.45,69,0.047),(3,76,0.040)):
            add('key',closing+offset,6.5,note,level,0.05,
                'closing: return of the opening motif')

    partials=[(1.0000,1.000,2.80),(2.0008,0.285,1.90),
              (3.0020,0.125,1.22),(4.0045,0.050,0.85),(5.0080,0.020,0.55)]

    def render_numpy(event):
        first=int(round(event['start']*rate))
        count=min(samples-first,int(math.ceil(event['length']*rate)))
        if count<=0:
            return
        t=np.arange(count,dtype=np.float64)/rate
        length,freq,amp,pan=(event[k] for k in ('length','frequency','amplitude','pan'))
        gl,gr=math.sqrt((1-pan)*0.5),math.sqrt((1+pan)*0.5)
        if event['kind']=='pad':
            attack,release=min(2.4,length*0.22),min(2.5,length*0.26)
            a=np.clip(t/max(0.01,attack),0,1)
            z=np.clip((length-t)/max(0.01,release),0,1)
            env=a*a*(3-2*a)*z*z*(3-2*z)
            env*=0.97+0.03*np.sin(TAU*0.085*t)
            phase=TAU*freq*t
            wl=(np.sin(phase*0.99955)+0.22*np.sin(phase*2.0002+0.3)
                +0.055*np.sin(phase*3.0010))
            wr=(np.sin(phase*1.00045+0.16)+0.22*np.sin(phase*1.9998+0.46)
                +0.055*np.sin(phase*2.9990+0.1))
            left[first:first+count]+=amp*gl*env*wl
            right[first:first+count]+=amp*gr*env*wr
        else:
            a=np.clip(t/0.028,0,1)
            z=np.clip((length-t)/0.70,0,1)
            env=a*a*(3-2*a)*z*z*(3-2*z)
            tone=np.zeros(count,dtype=np.float64)
            for ratio,weight,decay in partials:
                tone+=weight*np.exp(-t/decay)*np.sin(TAU*freq*ratio*t)
            tone+=0.10*np.exp(-t/2.15)*np.sin(TAU*freq*1.0008*t+0.04)
            tone*=amp*env
            left[first:first+count]+=gl*tone
            right[first:first+count]+=gr*tone

    def render_standard(event):
        first=int(round(event['start']*rate))
        count=min(samples-first,int(math.ceil(event['length']*rate)))
        if count<=0:
            return
        length,freq,amp,pan=(event[k] for k in ('length','frequency','amplitude','pan'))
        gl,gr=math.sqrt((1-pan)*0.5),math.sqrt((1+pan)*0.5)
        sine,exp,inv=math.sin,math.exp,1/rate
        if event['kind']=='pad':
            attack,release=min(2.4,length*0.22),min(2.5,length*0.26)
            for i in range(count):
                t=i*inv
                env=smoothstep(t/max(0.01,attack))*smoothstep((length-t)/max(0.01,release))
                env*=0.97+0.03*sine(TAU*0.085*t)
                phase=TAU*freq*t
                wl=sine(phase*0.99955)+0.22*sine(phase*2.0002+0.3)+0.055*sine(phase*3.0010)
                wr=sine(phase*1.00045+0.16)+0.22*sine(phase*1.9998+0.46)+0.055*sine(phase*2.9990+0.1)
                left[first+i]+=amp*env*gl*wl
                right[first+i]+=amp*env*gr*wr
        else:
            for i in range(count):
                t=i*inv
                env=smoothstep(t/0.028)*smoothstep((length-t)/0.70)
                phase=TAU*freq*t
                tone=sum(weight*exp(-t/decay)*sine(phase*ratio)
                         for ratio,weight,decay in partials)
                tone+=0.10*exp(-t/2.15)*sine(phase*1.0008+0.04)
                tone*=amp*env
                left[first+i]+=gl*tone
                right[first+i]+=gr*tone

    render=render_numpy if np is not None else render_standard
    for number,event in enumerate(events,1):
        render(event)
        if number%12==0 or number==len(events):
            print(json.dumps({'rendered_events':number,'total_events':len(events),
                              'backend':'numpy' if np is not None else 'stdlib'}),flush=True)

    reflections=[(0.073,0.100),(0.131,0.067),(0.211,0.042),
                 (0.337,0.027),(0.499,0.016),(0.701,0.009)]
    if np is not None:
        dry_l,dry_r=left.copy(),right.copy()
        for delay,gain in reflections:
            shift=int(round(delay*rate))
            if shift<samples:
                left[shift:]+=gain*dry_r[:-shift]
                right[shift:]+=gain*dry_l[:-shift]
        t=np.arange(samples,dtype=np.float64)/rate
        opening=np.clip(t/1.8,0,1)
        closing=np.clip((duration-t)/4.2,0,1)
        fade=opening*opening*(3-2*opening)*closing*closing*(3-2*closing)
        left*=fade
        right*=fade
        peak=max(float(np.max(np.abs(left))),float(np.max(np.abs(right))))
    else:
        dry_l,dry_r=array.array('d',left),array.array('d',right)
        for delay,gain in reflections:
            shift=int(round(delay*rate))
            for i in range(shift,samples):
                left[i]+=gain*dry_r[i-shift]
                right[i]+=gain*dry_l[i-shift]
        peak=0.0
        for i in range(samples):
            t=i/rate
            fade=smoothstep(t/1.8)*smoothstep((duration-t)/4.2)
            left[i]*=fade
            right[i]*=fade
            peak=max(peak,abs(left[i]),abs(right[i]))
    if peak<=0:
        raise ValueError('Synthesis unexpectedly produced silence.')
    gain=10**(args.peak_dbfs/20)/peak
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(output_path),'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for first in range(0,samples,16384):
            last=min(samples,first+16384)
            if np is not None:
                stereo=np.empty((last-first,2),dtype=np.float64)
                stereo[:,0]=left[first:last]*gain
                stereo[:,1]=right[first:last]*gain
                pcm=np.rint(np.clip(stereo,-1,1)*32767).astype('<i2')
                wav.writeframesraw(pcm.tobytes())
            else:
                pcm=array.array('h')
                for i in range(first,last):
                    for channel in (left,right):
                        pcm.append(int(round(max(-1,min(1,channel[i]*gain))*32767)))
                if sys.byteorder!='little':
                    pcm.byteswap()
                wav.writeframesraw(pcm.tobytes())
    receipt={'title':'CasePath — A clear path',
             'type':'Original deterministic additive synthesis',
             'recordings_used':False,'network_used':False,'model_or_provider_calls':False,
             'timeline_file':str(timeline_path),
             'timeline_sha256':hashlib.sha256(timeline_path.read_bytes()).hexdigest(),
             'output_file':str(output_path),
             'output_sha256':hashlib.sha256(output_path.read_bytes()).hexdigest(),
             'duration_seconds':duration,'sample_rate':rate,'channels':2,'pcm_bits':16,
             'backend':'numpy' if np is not None else 'stdlib',
             'peak_target_dbfs':args.peak_dbfs,'loudness_lufs':None,
             'loudness_note':'Peak normalized only; measure and master loudness separately.',
             'editorial_note':'Cues mark presentation acts, not new application operations.',
             'acts':acts,'events':events}
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'written':str(output_path),'receipt':str(receipt_path),
                      'seconds':duration,'sample_rate':rate,'events':len(events),
                      'peak_target_dbfs':args.peak_dbfs,'backend':receipt['backend']}),flush=True)


if __name__=='__main__':
    main()
