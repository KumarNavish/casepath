#!/usr/bin/env python3
"""Two-pass loudness master and lossless-video mux for the CasePath film.

Preserves source files, copies video packets without re-encoding, and verifies
the decoded output and measured final AAC audio. No network or provider use.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--silent', required=True)
    parser.add_argument('--score', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--preview', help='Optional new 10-second PCM WAV path.')
    parser.add_argument('--preview-start', type=float, default=0.0)
    parser.add_argument('--expected-frames', type=int, default=2957)
    parser.add_argument('--ffmpeg', default=str(Path.home()/'.local/bin/ffmpeg'))
    parser.add_argument('--ffprobe', default=str(Path.home()/'.local/bin/ffprobe'))
    args = parser.parse_args()
    silent, score, out = map(lambda p: Path(p).resolve(),
                             (args.silent, args.score, args.out))
    preview = Path(args.preview).resolve() if args.preview else None
    evidence = out.parent / (out.stem + '-media-evidence')
    receipt_path = out.with_suffix('.media.json')
    for p in (out, receipt_path, evidence, preview):
        if p and p.exists():
            raise FileExistsError('Preserve previous outputs; choose a new path: '+str(p))
    for p in (silent, score):
        if not p.is_file():
            raise FileNotFoundError(p)
    if out in (silent, score) or preview in (silent, score):
        raise ValueError('Output must not replace an input.')
    evidence.mkdir(parents=True)
    original_hashes = {'silent': digest(silent), 'score': digest(score)}
    report = {
        'schema': 1, 'passed': False, 'silent': str(silent), 'score': str(score),
        'output': str(out), 'input_sha256': original_hashes, 'commands': [],
        'targets': {'integrated_lufs': -20.0, 'final_true_peak_ceiling_dbtp': -2.0,
                    'pcm_true_peak_target_dbtp': -2.5, 'lra_target_lu': 11.0},
        'listened_by_this_helper': False, 'video_reencoding': False,
        'note': 'The PCM master has 0.5 dB additional headroom for AAC overshoot.'
    }

    def run(name, argv):
        result = subprocess.run(argv, capture_output=True, text=True)
        (evidence/(name+'.stdout.txt')).write_text(result.stdout)
        (evidence/(name+'.stderr.txt')).write_text(result.stderr)
        report['commands'].append({'name': name, 'argv': argv,
                                    'exit_code': result.returncode})
        if result.returncode:
            raise RuntimeError(name+' failed; inspect '+str(evidence/(name+'.stderr.txt')))
        return result

    def probe(name, filename, count=False):
        argv = [args.ffprobe, '-v', 'error']
        if count:
            argv += ['-count_frames']
        argv += ['-show_streams', '-show_format', '-of', 'json', str(filename)]
        return json.loads(run(name, argv).stdout)

    def norm_stats(text):
        blocks = re.findall(r'\{\s*"input_i".*?\}', text, flags=re.S)
        if not blocks:
            raise ValueError('No loudnorm measurement JSON was returned.')
        block = json.loads(blocks[-1])
        for key in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset'):
            if not math.isfinite(float(block[key])):
                raise ValueError('Nonfinite audio measurement: '+key)
        return block

    def video_hash(name, filename):
        text = run(name, [args.ffmpeg, '-nostdin', '-hide_banner', '-v', 'error',
                         '-i', str(filename), '-map', '0:v:0', '-c:v', 'copy',
                         '-f', 'hash', '-hash', 'sha256', 'pipe:1']).stdout.strip()
        if not re.fullmatch(r'SHA256=[0-9a-fA-F]{64}', text):
            raise ValueError('Unexpected encoded-video hash output: '+text)
        return text.split('=', 1)[1].lower()

    try:
        before = probe('01-source-video-probe', silent)
        source_video = [s for s in before['streams'] if s['codec_type']=='video']
        if len(source_video)!=1 or len(before['streams'])!=1:
            raise ValueError('Expected exactly one silent video stream.')
        v = source_video[0]
        assert v['codec_name']=='h264'
        assert (v['width'],v['height'])==(1920,1080)
        assert v['avg_frame_rate']=='30/1'
        frames = int(v['nb_frames'])
        assert frames==args.expected_frames, (frames,args.expected_frames)
        duration = frames/30.0
        assert abs(float(v['duration'])-duration)<1e-5
        pcm_samples = frames*1600  # 48,000 / 30: exact integer alignment
        report['duration_seconds'] = duration
        report['video_frames'] = frames
        report['audio_pcm_samples'] = pcm_samples
        report['source_video_probe'] = before
        report['source_score_probe'] = probe('02-source-score-probe', score)

        source_audio = [s for s in report['source_score_probe']['streams']
                        if s['codec_type']=='audio']
        assert len(source_audio)==1 and int(source_audio[0]['channels'])==2
        assert abs(float(source_audio[0]['duration'])-duration)<0.1, (
            'Score duration must already match the film within 100 ms.')

        # Resample before trimming by samples; apad handles subframe rounding.
        base = 'aresample=48000,apad,atrim=end_sample='+str(pcm_samples)
        target = 'I=-20:TP=-2.5:LRA=11'
        first = run('03-loudnorm-pass1', [
            args.ffmpeg,'-nostdin','-hide_banner','-i',str(score),'-map','0:a:0',
            '-af',base+',loudnorm='+target+':print_format=json','-f','null','-'])
        measured = norm_stats(first.stderr)
        report['first_pass'] = measured
        (evidence/'loudness-pass1.json').write_text(json.dumps(measured,indent=2)+'\n')
        filter2 = (
            base+',loudnorm='+target+
            ':measured_I='+measured['input_i']+
            ':measured_LRA='+measured['input_lra']+
            ':measured_TP='+measured['input_tp']+
            ':measured_thresh='+measured['input_thresh']+
            ':offset='+measured['target_offset']+
            ':linear=true:print_format=json,aresample=48000,'+
            'apad,atrim=end_sample='+str(pcm_samples))
        master = evidence/'score-master-48k.wav'
        second = run('04-loudnorm-pass2', [
            args.ffmpeg,'-nostdin','-hide_banner','-i',str(score),'-map','0:a:0',
            '-af',filter2,'-ar','48000','-ac','2','-c:a','pcm_s24le',str(master)])
        report['second_pass'] = norm_stats(second.stderr)
        report['pcm_master_sha256'] = digest(master)

        # Only audio is encoded. Existing H.264 packets are copied unchanged.
        run('05-mux', [
            args.ffmpeg,'-nostdin','-hide_banner','-v','error',
            '-i',str(silent),'-i',str(master),'-map','0:v:0','-map','1:a:0',
            '-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-ac','2',
            '-t',format(duration,'.9f'),'-map_metadata','-1',
            '-metadata','title=CasePath','-movflags','+faststart',str(out)])

        after = probe('06-output-probe', out, count=True)
        report['output_probe'] = after
        videos = [s for s in after['streams'] if s['codec_type']=='video']
        audios = [s for s in after['streams'] if s['codec_type']=='audio']
        assert len(videos)==len(audios)==1 and len(after['streams'])==2
        ov, oa = videos[0], audios[0]
        assert ov['codec_name']==v['codec_name']=='h264'
        assert (ov['width'],ov['height'])==(1920,1080)
        assert ov['avg_frame_rate']=='30/1'
        assert int(ov['nb_frames'])==int(ov['nb_read_frames'])==frames
        assert abs(float(ov['duration'])-duration)<1e-5
        assert oa['codec_name']=='aac' and int(oa['channels'])==2
        assert int(oa['sample_rate'])==48000
        assert abs(float(oa.get('start_time',0)))<=1/48000+1e-6
        assert abs(float(oa['duration'])-duration)<=1024/48000+0.001

        original_video_hash = video_hash('07-original-video-packets', silent)
        output_video_hash = video_hash('08-output-video-packets', out)
        report['encoded_video_sha256'] = {
            'source': original_video_hash, 'output': output_video_hash}
        assert original_video_hash==output_video_hash, 'Video packets changed.'

        run('09-full-decode', [args.ffmpeg,'-nostdin','-hide_banner','-v','error',
                              '-xerror','-i',str(out),'-map','0:v:0',
                              '-map','0:a:0','-f','null','-'])
        final_measure = run('10-final-aac-loudness', [
            args.ffmpeg,'-nostdin','-hide_banner','-i',str(out),'-map','0:a:0',
            '-af','loudnorm=I=-20:TP=-2:LRA=11:print_format=json',
            '-f','null','-'])
        final_stats = norm_stats(final_measure.stderr)
        report['final_aac_measurement'] = final_stats
        report['measured_integrated_lufs'] = float(final_stats['input_i'])
        report['measured_true_peak_dbtp'] = float(final_stats['input_tp'])
        assert abs(report['measured_integrated_lufs']+20.0)<=0.5, (
            'Final audio is outside -20 +/- 0.5 LUFS; preserve outputs and inspect.')
        assert report['measured_true_peak_dbtp']<=-2.0, (
            'Final AAC exceeds -2 dBTP; preserve output and master with more headroom.')

        if preview:
            if not 0<=args.preview_start<=duration-10:
                raise ValueError('Preview start must allow a complete 10-second excerpt.')
            preview.parent.mkdir(parents=True,exist_ok=True)
            run('11-listening-preview', [
                args.ffmpeg,'-nostdin','-hide_banner','-v','error','-i',str(out),
                '-ss',str(args.preview_start),'-t','10','-map','0:a:0',
                '-c:a','pcm_s16le','-ar','48000','-ac','2',str(preview)])
            report['preview'] = {'path': str(preview),'start': args.preview_start,
                                 'duration': 10,'sha256':digest(preview)}
        assert digest(silent)==original_hashes['silent']
        assert digest(score)==original_hashes['score']
        report['output_sha256'] = digest(out)
        report['output_bytes'] = out.stat().st_size
        report['originals_unchanged'] = True
        report['passed'] = True
    except Exception as error:
        report['failure'] = repr(error)
    finally:
        receipt_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'output':str(out),
                      'receipt':str(receipt_path),
                      'lufs':report.get('measured_integrated_lufs'),
                      'true_peak_dbtp':report.get('measured_true_peak_dbtp'),
                      'failure':report.get('failure')}))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    sys.exit(main())
