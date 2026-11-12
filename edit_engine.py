"""Non-destructive single-track editing and local speech recognition."""
import copy, hashlib, json, math, os, re, shutil, subprocess, tempfile, time, uuid, zipfile
from pathlib import Path
import requests
import engine as E

class Cancelled(Exception): pass

def run(args, cancel=None, cwd=None):
    with tempfile.TemporaryFile() as log:
        p=subprocess.Popen([str(x) for x in args],stdout=log,stderr=log,cwd=cwd,creationflags=0x08000000 if os.name=='nt' else 0)
        while p.poll() is None:
            if cancel and cancel.is_set():p.kill();p.wait();raise Cancelled('Cancelled')
            time.sleep(.08)
        if p.returncode:
            log.seek(0);raise RuntimeError(log.read().decode('utf-8','replace')[-2500:])

def new_clip(path):
    path=Path(path).resolve();info=E.inspect_video(path)
    if not any(s.get('codec_type')=='video' for s in info['streams']):raise ValueError('No video stream / 文件没有视频轨')
    duration=float(info.get('format',{}).get('duration',0))
    if not math.isfinite(duration) or duration<=0:raise ValueError('Invalid duration / 无效时长')
    return dict(id=uuid.uuid4().hex,path=str(path),duration=duration,start=0.,end=duration)

def validate_clips(clips):
    if not clips:raise ValueError('Add videos first / 请先添加视频')
    for c in clips:
        start,end,duration=map(float,(c['start'],c['end'],c['duration']))
        if not all(map(math.isfinite,(start,end,duration))) or not 0<=start<end<=duration+.05:raise ValueError('Invalid trim range / 裁剪范围无效')
        if not Path(c['path']).is_file():raise ValueError('Missing video / 视频不存在: '+c['path'])

def total_duration(clips):return sum(c['end']-c['start'] for c in clips)

def split_clip(clips,index,position):
    result=copy.deepcopy(clips);c=result[index]
    if not c['start']+.05<position<c['end']-.05:raise ValueError('Split inside the clip / 请在片段内部选择分割点')
    right=copy.deepcopy(c);right.update(id=uuid.uuid4().hex,start=position);c['end']=position;result.insert(index+1,right);return result

def normalize(clip,target,size,cancel=None):
    info=E.inspect_video(clip['path']);audio=any(s.get('codec_type')=='audio' for s in info['streams']);duration=clip['end']-clip['start']
    args=[E.ffmpeg_path(),'-hide_banner','-loglevel','error','-y','-ss',str(clip['start']),'-i',clip['path']]
    if not audio:args+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
    w,h=size
    args+=['-map','0:v:0','-map','0:a:0' if audio else '1:a:0','-vf',f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30','-af','aresample=48000,asetpts=PTS-STARTPTS,apad','-t',str(duration),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-movflags','+faststart',str(target)]
    run(args,cancel)

def timestamp(seconds):
    n=round(float(seconds)*1000);return f'{n//3600000:02d}:{n//60000%60:02d}:{n//1000%60:02d},{n%1000:03d}'

def srt_text(cues,duration=None):
    lines=[]
    for i,c in enumerate(cues,1):
        a,b=float(c['start']),float(c['end']);text=str(c['text']).strip()
        if not math.isfinite(a) or not math.isfinite(b) or not 0<=a<b or (duration is not None and b>duration+.2):raise ValueError('Invalid subtitle times / 字幕时间无效')
        if text:lines.append(f'{i}\n{timestamp(a)} --> {timestamp(b)}\n{text}\n')
    return '\n'.join(lines)

def parse_srt(text):
    cues=[]
    def secs(t):
        h,m,s=re.split('[:,.]',t)[:3];ms=re.split('[:,.]',t)[3];return int(h)*3600+int(m)*60+int(s)+int(ms)/1000
    for block in re.split(r'\n\s*\n',text.replace('\r','').strip()):
        lines=block.splitlines();idx=next((i for i,x in enumerate(lines) if '-->' in x),None)
        if idx is None:continue
        match=re.fullmatch(r'\s*(\d+:\d+:\d+[,\.]\d{3})\s*-->\s*(\d+:\d+:\d+[,\.]\d{3})\s*',lines[idx])
        if match:cues.append(dict(start=secs(match[1]),end=secs(match[2]),text='\n'.join(lines[idx+1:])))
    if not cues:raise ValueError('No valid SRT captions / 没有有效的 SRT 字幕')
    srt_text(cues);return cues

def export_video(clips,destination,size=(1280,720),cues=None,burn=False,emit=lambda x:None,cancel=None):
    validate_clips(clips);destination=Path(destination).resolve()
    if any(Path(c['path']).resolve()==destination for c in clips):raise ValueError('Choose a new output file / 请勿覆盖素材原片')
    destination.parent.mkdir(parents=True,exist_ok=True);cues=cues or [];subtitle=srt_text(cues,total_duration(clips))
    with tempfile.TemporaryDirectory(prefix='cve_edit_',dir=destination.parent) as td:
        td=Path(td)
        for i,c in enumerate(clips):
            emit(f'{i+1}/{len(clips)}');normalize(c,td/f'{i:04d}.mp4',size,cancel)
        (td/'concat.txt').write_text(''.join(f"file '{i:04d}.mp4'\n" for i in range(len(clips))),encoding='utf-8')
        run([E.ffmpeg_path(),'-v','error','-y','-f','concat','-safe','0','-i','concat.txt','-c','copy','joined.mp4'],cancel,cwd=td)
        result=td/'joined.mp4'
        if subtitle:
            (td/'captions.srt').write_text(subtitle,encoding='utf-8')
            if burn:
                # A fixed relative filename avoids escaping user paths inside FFmpeg filters.
                args=['-i','joined.mp4','-vf',"subtitles=captions.srt:force_style='FontName=Microsoft YaHei,FontSize=22,Outline=1,MarginV=22'",'-c:v','libx264','-preset','fast','-crf','20','-c:a','copy']
            else:args=['-i','joined.mp4','-i','captions.srt','-map','0:v','-map','0:a','-map','1:0','-c:v','copy','-c:a','copy','-c:s','mov_text']
            run([E.ffmpeg_path(),'-v','error','-y',*args,'-movflags','+faststart','final.mp4'],cancel,cwd=td);result=td/'final.mp4'
        if cancel and cancel.is_set():raise Cancelled('Cancelled')
        # Keep prior output until all processing succeeds.
        os.replace(result,destination)
    return str(destination)

WHISPER_URL='https://github.com/ggml-org/whisper.cpp/releases/download/v1.8.2/whisper-bin-x64.zip'
WHISPER_SHA='b1514ebc099765e39fa37eb780b92a140a94c86bb0b3b3d98226b38825979732'
MODEL_URL='https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin'
MODEL_SHA='60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe'

def asr_paths(root):
    root=Path(root);exe=next(root.glob('bin/**/whisper-cli.exe'),None);return exe,root/'ggml-base.bin'

def download(url,path,sha,cancel,emit):
    session=requests.Session();session.trust_env=False;part=Path(str(path)+'.part');digest=hashlib.sha256()
    try:
        with session.get(url,stream=True,timeout=(20,60)) as response:
            response.raise_for_status();size=int(response.headers.get('content-length',0));n=0;last=0
            with part.open('wb') as f:
                for chunk in response.iter_content(1024*1024):
                    if cancel and cancel.is_set():raise Cancelled('Cancelled')
                    f.write(chunk);digest.update(chunk);n+=len(chunk)
                    if time.monotonic()-last>1:emit(f'{n//1048576} MB'+(f' / {size//1048576} MB' if size else ''));last=time.monotonic()
        if digest.hexdigest()!=sha:raise ValueError('Download checksum mismatch / 下载校验失败')
        os.replace(part,path)
    finally:
        if part.exists():part.unlink()

def install_asr(root,cancel=None,emit=lambda x:None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);exe,model=asr_paths(root)
    if not exe:
        archive=root/'whisper.zip';download(WHISPER_URL,archive,WHISPER_SHA,cancel,emit);target=(root/'bin').resolve()
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if not (target/member.filename).resolve().is_relative_to(target):raise ValueError('Unsafe archive')
            z.extractall(target)
        archive.unlink()
    if not model.exists():download(MODEL_URL,model,MODEL_SHA,cancel,emit)
    exe,model=asr_paths(root)
    if exe is None:raise ValueError('whisper-cli.exe missing')
    return exe,model

def recognize(clips,root,cancel=None,emit=lambda x:None,language='zh'):
    validate_clips(clips);exe,model=asr_paths(root)
    if not exe or not model.exists():raise ValueError('Install subtitle components first / 请先下载字幕识别组件')
    cues=[];offset=0
    root=Path(root).resolve();exe=exe.resolve()
    with tempfile.TemporaryDirectory(prefix='cve_asr_',dir=root) as td:
        td=Path(td)
        for i,c in enumerate(clips):
            duration=c['end']-c['start'];emit(f'{i+1}/{len(clips)}');info=E.inspect_video(c['path'])
            if any(s.get('codec_type')=='audio' for s in info['streams']):
                audio=td/'audio.wav';base=td/'speech'
                run([E.ffmpeg_path(),'-v','error','-y','-ss',str(c['start']),'-i',c['path'],'-t',str(duration),'-vn','-ar','16000','-ac','1','-c:a','pcm_s16le',audio],cancel)
                srt=td/'speech.srt'
                if srt.exists():srt.unlink()
                run([exe,'-m',model.name,'-f',audio.relative_to(root),'-l',language,'-osrt','-of',base.relative_to(root),'-ng','-t',str(min(8,os.cpu_count() or 4))],cancel,cwd=root)
                if srt.exists() and srt.read_text('utf-8-sig').strip():
                    for cue in parse_srt(srt.read_text('utf-8-sig')):
                        a=max(0,cue['start']);b=min(duration,cue['end'])
                        if a<b:cues.append(dict(start=a+offset,end=b+offset,text=cue['text']))
            offset+=duration
    return cues
