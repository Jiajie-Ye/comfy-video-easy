"""ComfyUI desktop client. No browser automation and no global queue mutation."""
from __future__ import annotations
import copy, hashlib, json, math, os, secrets, shutil, subprocess, sys, tempfile, time, uuid
from pathlib import Path
from urllib.parse import urlparse
import requests

SERVER = 'http://127.0.0.1:8188'
APP_VERSION = '0.6.4'
RATIOS = {'横屏 16:9':'16:9 (Widescreen)', '竖屏 9:16':'9:16 (Portrait Widescreen)', '方形 1:1':'1:1 (Square)', '竖图 2:3':'2:3 (Portrait Photo)'}
MAX_SEED = 2**53-1

def resource(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / name

def atomic_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)

def defaults():
    return dict(server=SERVER, prompt='', seconds=10., ratio='横屏 16:9', megapixels=.4,
                steps=8, sampler='euler', scheduler='beta', denoise=1., fixed=False, seed=12345,
                second=False, second_mp=.8, second_steps=4, second_denoise=.2,
                second_fixed=True, second_seed=12345, ref_size='max', resize='lanczos',
                video_audio=False, first_frame='', images=[], audios=[], videos=[])

def validate_settings(c):
    if urlparse(c['server']).scheme not in ('http','https') or not urlparse(c['server']).hostname:
        raise ValueError('服务器地址应以 http:// 或 https:// 开头。')
    if not str(c['prompt']).strip(): raise ValueError('请先填写视频描述（Prompt）。')
    if c['ratio'] not in RATIOS: raise ValueError('请选择画面比例。')
    for name,lo,hi in [('seconds',1,15),('megapixels',.1,2),('second_mp',.1,2),('steps',1,50),('second_steps',1,50),('denoise',.01,1),('second_denoise',.01,1)]:
        v=float(c[name])
        if not math.isfinite(v) or not lo<=v<=hi: raise ValueError(f'{name} 必须在 {lo} 到 {hi} 之间。')
    for key in ['seed','second_seed']:
        if not 0<=int(c[key])<=MAX_SEED: raise ValueError('种子必须为 0 到 9007199254740991 的整数。')
    for key,limit in [('images',9),('audios',3),('videos',3)]:
        if len(c[key])>limit: raise ValueError(f'{key} 最多 {limit} 个文件。')
    if c.get('first_frame') and c['first_frame'] not in c['images']:raise ValueError('首帧图片已不在参考图片列表中，请重新选择。 / First-frame image is missing from references.')
    if c['ref_size'] not in ('match','max'): raise ValueError('参考图尺寸模式无效。')
    if c['resize'] not in ('lanczos','bicubic','nvidia_rtx_vsr'): raise ValueError('二采缩放算法无效。')

def frame_count(seconds):
    # Positive rounding matches the workflow's round(a * 24) at UI precision.
    n=max(5,round(float(seconds)*24)); return n+(5-n%17)%17

def concrete_settings(c):
    c=copy.deepcopy(c); validate_settings(c)
    if not c['fixed']: c['seed']=secrets.randbelow(MAX_SEED)
    if not c['second_fixed']: c['second_seed']=secrets.randbelow(MAX_SEED)
    return c

def model_profile():
    return json.loads(resource('profile.json').read_text(encoding='utf-8'))

def build_prompt(c, uploaded, job_id, profile=None):
    """Explicit API graph of the existing reference-video branch and refinement.

    UI-only Set/Get/Reroute/Bypasser nodes are resolved. Unselected references are
    omitted, not inherited from the server owner's saved sample material.
    """
    profile=profile or model_profile(); p={}
    def add(i, typ, **inputs): p[str(i)]={'class_type':typ,'inputs':inputs}; return [str(i),0]
    vvae=add(5,'VAELoader',vae_name=profile['video_vae'])
    avae=add(6,'VAELoader',vae_name=profile['audio_vae'])
    clip=add(4,'CLIPLoader',clip_name=profile['clip'],type='minimax',device='default')
    base=add(9,'UNETLoader',unet_name=profile['model'],weight_dtype='default')
    # #125 is bypassed in the captured source, so the reference branch uses #9 directly.
    model=add(187,'LoraLoaderModelOnly',model=base,lora_name=profile['lora'],strength_model=1.)
    add(105,'ResolutionSelector',aspect_ratio=RATIOS[c['ratio']],megapixels=float(c['megapixels']),multiple=32)
    refs={}
    for i,name in enumerate(uploaded.get('images',[])):
        a=add(1000+i*2,'LoadImage',image=name)
        b=add(1001+i*2,'LayerUtility: ImageScaleByAspectRatio V2',image=a,
              aspect_ratio='original',proportional_width=1,proportional_height=1,fit='crop',
              method='lanczos',round_to_multiple='32',scale_to_side='total_pixel(kilo pixel)',
              scale_to_length=1536,background_color='#000000')
        refs[f'ref_images.ref_image_{i}']=b
    for i,name in enumerate(uploaded.get('audios',[])):
        refs[f'ref_audios.ref_audio_{i}']=add(1100+i,'LoadAudio',audio=name)
    for i,name in enumerate(uploaded.get('videos',[])):
        # Model's own schema requires reference video at 24fps, 2–15 seconds.
        a=add(1200+i,'VHS_LoadVideo',video=name,force_rate=24,custom_width=0,custom_height=0,
              frame_load_cap=360,skip_first_frames=0,select_every_nth=1,format='None')
        refs[f'ref_videos.ref_video_{i}']=a
        if c['video_audio']: refs[f'ref_video_audios.ref_video_audio_{i}']=[str(1200+i),2]
    cond=add(108,'MiniMaxH3ReferenceToVideo',clip=clip,vae=vvae,audio_vae=avae,prompt=c['prompt'],
             width=['105',0],height=['105',1],length=frame_count(c['seconds']),ref_image_size=c['ref_size'],**refs)
    base_cond=cond
    first_index=None
    if c.get('first_frame'):
        if c['first_frame'] not in c['images']:raise ValueError('首帧图片不在参考列表中 / First-frame image is missing')
        first_index=c['images'].index(c['first_frame'])
        if first_index>=len(uploaded.get('images',[])):raise ValueError('首帧图片尚未上传 / First-frame image was not uploaded')
        cond=add(109,'MiniMaxH3AddGuide',positive=base_cond,latent=['108',1],vae=vvae,image=[str(1000+first_index*2),0],frame_idx=0)
    noise=add(243,'RandomNoise',noise_seed=int(c['seed']))
    guider=add(246,'BasicGuider',model=model,conditioning=cond)
    sampler=add(249,'KSamplerSelect',sampler_name=c['sampler'])
    sched=add(248,'BasicScheduler',model=model,scheduler=c['scheduler'],steps=int(c['steps']),denoise=float(c['denoise']))
    latent=add(247,'SamplerCustomAdvanced',noise=noise,guider=guider,sampler=sampler,sigmas=sched,latent_image=['108',1])
    images=add(367,'VAEDecode',samples=latent,vae=vvae)
    audio=add(366,'VAEDecodeAudio',samples=latent,vae=avae)
    def output(i,im,au,label):
        return add(i,'VHS_VideoCombine',images=im,audio=au,frame_rate=24,loop_count=0,
                   filename_prefix=f'ComfyVideoEasy/{job_id}/{label}',format='video/h264-mp4',
                   pix_fmt='yuv420p',crf=19,save_metadata=True,trim_to_audio=False,pingpong=False,save_output=True)
    output(356,images,audio,'stage1')
    if c['second']:
        add(297,'ResolutionSelector',aspect_ratio=RATIOS[c['ratio']],megapixels=float(c['second_mp']),multiple=32)
        resized=add(291,'ImageResizeKJv2',image=images,width=['297',0],height=['297',1],
                    upscale_method=c['resize'],keep_proportion='crop',pad_color='0, 0, 0',
                    crop_position='center',divisible_by=0,device='cpu')
        vl=add(292,'VAEEncode',pixels=resized,vae=vvae)
        al=add(288,'VAEEncodeAudio',audio=audio,vae=avae)
        joined=add(293,'PT_H3ConcatAVLatent',video_latent=vl,audio_latent=al)
        noise2=add(300,'RandomNoise',noise_seed=int(c['second_seed']))
        second_cond=base_cond
        if first_index is not None:second_cond=add(299,'MiniMaxH3AddGuide',positive=base_cond,latent=joined,vae=vvae,image=[str(1000+first_index*2),0],frame_idx=0)
        guide2=add(294,'BasicGuider',model=base,conditioning=second_cond)
        sampler2=add(289,'KSamplerSelect',sampler_name=c['sampler'])
        sched2=add(290,'BasicScheduler',model=base,scheduler=c['scheduler'],steps=int(c['second_steps']),denoise=float(c['second_denoise']))
        latent2=add(295,'SamplerCustomAdvanced',noise=noise2,guider=guide2,sampler=sampler2,sigmas=sched2,latent_image=joined)
        im2=add(296,'VAEDecode',samples=latent2,vae=vvae)
        au2=add(358,'VAEDecodeAudio',samples=latent2,vae=avae)
        output(360,im2,au2,'stage2')
    return p

def validate_graph(p, schema):
    """Check links, server-required inputs and model enums without queuing a GPU job."""
    for nid,n in p.items():
        cls=n['class_type']
        if cls not in schema: raise ValueError(f'服务器缺少节点：{cls}')
        definitions=schema[cls]['input']
        for key,spec in definitions.get('required',{}).items():
            if key not in n['inputs']: raise ValueError(f'{cls} 缺少输入：{key}')
        for key,value in n['inputs'].items():
            spec=definitions.get('required',{}).get(key) or definitions.get('optional',{}).get(key)
            if isinstance(value,list) and len(value)==2 and isinstance(value[1],int):
                src=str(value[0]); slot=value[1]
                if src not in p: raise ValueError(f'{nid} 引用了不存在的节点 {src}')
                outputs=schema[p[src]['class_type']]['output']
                if not 0<=slot<len(outputs): raise ValueError(f'{src} 输出编号错误。')
            elif spec:
                choices=spec[0] if isinstance(spec[0],list) else (spec[1].get('options') if len(spec)>1 and isinstance(spec[1],dict) else None)
                if choices is not None and value not in choices:
                    raise ValueError(f'{cls}.{key} 的选项在服务器不存在：{value}')

class Client:
    def __init__(self,url=SERVER):
        self.url=url.rstrip('/'); self.session=requests.Session(); self.session.trust_env=False
    def json(self,path,data=None,timeout=30):
        try:
            r=self.session.get(self.url+path,timeout=timeout) if data is None else self.session.post(self.url+path,json=data,timeout=timeout)
            if not r.ok:
                raise RuntimeError(f'服务器返回 {r.status_code}：{r.text[:2500]}')
            return r.json()
        except requests.RequestException as exc:
            raise ConnectionError('无法连接服务器。请确认网络可达、服务器在线。\n'+str(exc)) from exc
    def upload(self,path):
        path=Path(path)
        if not path.is_file(): raise FileNotFoundError(f'找不到素材：{path}')
        # Content-addressed names prevent collisions and preserve reusable graph inputs.
        h=hashlib.sha256()
        with path.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
        name='cve_'+h.hexdigest()+path.suffix.lower()
        with path.open('rb') as f:
            r=self.session.post(self.url+'/upload/image',files={'image':(name,f,'application/octet-stream')},data={'type':'input','overwrite':'false'},timeout=(15,300))
        if not r.ok: raise RuntimeError(f'上传失败：{r.status_code} {r.text[:600]}')
        d=r.json(); return '/'.join(x for x in [d.get('subfolder',''),d['name']] if x)
    def submit(self,p,job_id):
        return self.json('/prompt',{'prompt':p,'client_id':job_id,'prompt_id':job_id},timeout=120)
    def status(self,prompt_id):
        history=self.json('/history/'+prompt_id)
        if prompt_id in history: return 'history',history[prompt_id]
        q=self.json('/queue')
        if any(x[1]==prompt_id for x in q.get('queue_running',[])):return 'running',None
        pending=q.get('queue_pending',[])
        for index,item in enumerate(pending):
            if item[1]==prompt_id:return 'pending',index+1
        return 'unknown',None
    def download(self,item,target):
        target=Path(target); temp=target.with_suffix(target.suffix+'.part')
        with self.session.get(self.url+'/view',params={k:item.get(k,'') for k in ('filename','subfolder','type')},stream=True,timeout=(15,120)) as r:
            r.raise_for_status()
            with temp.open('wb') as f:
                for chunk in r.iter_content(1024*1024): f.write(chunk)
        temp.replace(target)

def result_media(history):
    """Only explicit output nodes from this job, never a global latest result."""
    found=[]
    for node,label in [('356','一采'),('360','二采')]:
        seen=set()
        for value in history.get('outputs',{}).get(node,{}).values():
            if not isinstance(value,list):continue
            for item in value:
                if not isinstance(item,dict):continue
                name=item.get('filename','')
                if not name.lower().endswith(('.mp4','.webm','.mov')):continue
                key=(name,item.get('subfolder',''),item.get('type','output'))
                if key in seen:continue
                seen.add(key); found.append((label,item))
    return found

def ffmpeg_path(name='ffmpeg.exe'):
    for candidate in [resource('ffmpeg')/name,resource(name)]:
        if candidate.is_file():return str(candidate)
    found=shutil.which(name)
    if found:return found
    raise FileNotFoundError(f'工具缺少 {name}，请使用完整打包版。')

def run_media(args):
    return subprocess.run(args,capture_output=True,encoding='utf-8',errors='replace',creationflags=0x08000000 if os.name=='nt' else 0)

def inspect_video(path):
    r=run_media([ffmpeg_path('ffprobe.exe'),'-v','error','-show_format','-show_streams','-of','json',str(path)])
    if r.returncode: raise ValueError('无法读取媒体：'+r.stderr[-600:])
    return json.loads(r.stdout)

def validate_media(c):
    allowed={'images':{'.png','.jpg','.jpeg','.webp','.bmp'},'audios':{'.mp3','.wav','.flac','.m4a','.ogg','.mp4'},'videos':{'.mp4','.mov','.mkv','.avi','.webm','.m4v'}}
    for group in allowed:
        for name in c[group]:
            f=Path(name)
            if not f.is_file():raise ValueError(f'素材不存在：{f}')
            if f.suffix.lower() not in allowed[group]:raise ValueError(f'不支持的{group}文件格式：{f.suffix}')
            if f.stat().st_size>500*1024*1024:raise ValueError('单个参考素材请小于 500 MB。')
    for name in c['videos']:
        d=inspect_video(name)
        duration=float(d.get('format',{}).get('duration',0))
        if not 2<=duration<=15.1:raise ValueError(f'参考视频需要 2–15 秒，请先裁切：{Path(name).name}（{duration:.1f} 秒）')
        if c['video_audio'] and not any(s.get('codec_type')=='audio' for s in d.get('streams',[])):
            raise ValueError('勾选了参考视频原声，但此视频没有音轨：'+Path(name).name)

def unique_path(path):
    path=Path(path); i=2; candidate=path
    while candidate.exists(): candidate=path.with_name(f'{path.stem}_{i}{path.suffix}');i+=1
    return candidate

def extract_last_frame(video,outdir):
    video=Path(video);outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    dest=unique_path(outdir/(video.stem+'_last_frame.png'))
    for tail in ['-0.001','-2']:
        with tempfile.TemporaryDirectory(prefix='cve_frame_') as td:
            r=run_media([ffmpeg_path(),'-hide_banner','-loglevel','error','-sseof',tail,'-i',str(video),'-map','0:v:0','-fps_mode','vfr','-y',str(Path(td)/'frame_%08d.png')])
            frames=sorted(Path(td).glob('frame_*.png'))
            if r.returncode==0 and frames:
                shutil.copyfile(frames[-1],dest);return dest
    raise RuntimeError('提取末帧失败：'+r.stderr[-800:])

def job_create(root,c,profile=None):
    jid=str(uuid.uuid4());folder=Path(root)/(time.strftime('%Y%m%d_%H%M%S')+'_'+jid[:8]);folder.mkdir(parents=True)
    job={'id':jid,'version':APP_VERSION,'created':time.strftime('%Y-%m-%d %H:%M:%S'),'settings':copy.deepcopy(c),
         'profile':profile or model_profile(),'status':'准备中','uploaded':{},'files':[],'folder':str(folder)}
    save_job(job);return job

def save_job(job):atomic_json(Path(job['folder'])/'task.json',job)

def prepare_and_submit(job,emit=lambda *_:None,reuse=None):
    c=job['settings'];client=Client(c['server'])
    if reuse is None:
        validate_media(c);uploads={}
        for group in ['images','audios','videos']:
            uploads[group]=[]
            for i,path in enumerate(c[group]):
                emit('status',f'正在上传 {group} {i+1}/{len(c[group])}：{Path(path).name}')
                uploads[group].append(client.upload(path))
    else: uploads=copy.deepcopy(reuse)
    job['uploaded']=uploads
    p=build_prompt(c,uploads,job['id'],job['profile']);schema=client.json('/object_info',timeout=60)
    validate_graph(p,schema)
    atomic_json(Path(job['folder'])/'api_prompt.json',p)
    # Persist ID BEFORE request. A timed-out POST may still be accepted: never auto-retry.
    job['prompt_id']=job['id'];job['status']='提交中';save_job(job)
    try:
        response=client.submit(p,job['id'])
        if not response.get('prompt_id'):raise RuntimeError(str(response)[:2000])
        job['prompt_id']=response['prompt_id'];job['status']='已提交';save_job(job)
    except Exception:
        job['status']='提交结果待确认';save_job(job);raise
    emit('status','任务已提交，正在排队或生成。')
    return job

def monitor(job,emit=lambda *_:None,stop=None,interval=3):
    client=Client(job['settings']['server']);failures=0;unknown=0
    while stop is None or not stop.is_set():
        try:
            state,data=client.status(job['prompt_id']);failures=0
            if state=='history':
                status=data.get('status',{})
                if status.get('status_str')=='error':
                    detail='\n'.join(str(v) for k,v in status.get('messages',[]) if k in ('execution_error','execution_interrupted'))
                    job['status']='生成失败';job['error']=detail;save_job(job)
                    raise RuntimeError('服务器生成失败：\n'+detail[:2200])
                if not status.get('completed',False):
                    emit('status','服务器正在记录结果…');time.sleep(interval);continue
                atomic_json(Path(job['folder'])/'server_result.json',data)
                items=result_media(data)
                if not items:raise RuntimeError('任务结束，但未发现视频输出。请查看任务目录中的 server_result.json。')
                outputs=[]
                for index,(label,item) in enumerate(items):
                    emit('status',f'正在下载{label}结果…')
                    filename=Path(item['filename'].replace('\\','/')).name
                    target=Path(job['folder'])/(label+'_'+filename)
                    client.download(item,target);outputs.append(str(target))
                job['files']=outputs;job['status']='已完成';save_job(job);return outputs
            if state=='unknown':
                unknown+=1
                if unknown>=10:raise RuntimeError('服务器未找到该任务，可能已重启或清理历史。任务信息已保留，可稍后继续查询。')
            else: unknown=0
            msg=f'排队中，当前等待位置 {data}' if state=='pending' else ('服务器正在生成，请耐心等待…' if state=='running' else '正在确认任务状态…')
            emit('status',msg)
        except (ConnectionError,requests.RequestException) as exc:
            failures+=1;emit('status','连接暂时中断，正在重新查询（不会重复提交）…')
            if failures>=20:raise ConnectionError('长时间无法连接。任务编号已保存，恢复网络后可从历史记录继续查询。') from exc
        if stop is not None:stop.wait(interval)
        else:time.sleep(interval)
    return None
