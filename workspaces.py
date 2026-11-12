"""Persistent per-user workspace location and non-destructive history roots."""
import json,os,shutil,tempfile
from pathlib import Path
import engine as E

def locator():return Path(os.environ.get('LOCALAPPDATA',Path.home()/'.config'))/'ComfyVideoEasy'/'workspace.json'
def default_workspace():return Path.home()/'Documents'/'AI视频助手工作区'
def remember(folder):E.atomic_json(locator(),{'workspace':str(Path(folder).resolve())})
def startup_workspace(executable_folder):
    try:
        saved=json.loads(locator().read_text('utf-8'));path=saved.get('workspace')
        if path:return Path(path)
    except (OSError,ValueError):pass
    legacy=Path(executable_folder)/'我的视频数据'
    if (legacy/'settings.json').is_file():return legacy
    return default_workspace()

def unique_roots(paths):
    result=[];seen=set()
    for path in paths:
        if not str(path).strip():continue
        key=os.path.normcase(str(Path(path).resolve()))
        if key not in seen:seen.add(key);result.append(str(Path(path).resolve()))
    return result

def import_roots(folder):
    folder=Path(folder).resolve();roots=[]
    for candidate in [folder,folder/'我的视频数据']:
        if (candidate/'settings.json').is_file():
            try:
                cfg=json.loads((candidate/'settings.json').read_text('utf-8'));roots.extend(cfg.get('history_roots',[]))
                if cfg.get('output'):roots.append(cfg['output'])
            except (OSError,ValueError):pass
        if (candidate/'视频作品').is_dir():roots.append(str(candidate/'视频作品'))
        if (candidate/'task.json').is_file():roots.append(str(candidate.parent))
        if next(candidate.glob('*/task.json'),None):roots.append(str(candidate))
    return unique_roots(roots)

def manifests(roots):
    found={}
    for root in unique_roots(roots):
        try:
            for p in Path(root).glob('*/task.json'):found[os.path.normcase(str(p.resolve()))]=p
        except OSError:continue
    return sorted(found.values(),key=lambda p:p.parent.name,reverse=True)

def resolve_job_files(job,folder):
    # Old copied task folders often contain usable files under new absolute paths.
    files=[]
    for raw in job.get('files',[]):
        p=Path(raw);local=Path(folder)/p.name
        files.append(str(p if p.is_file() else local if local.is_file() else p))
    job['files']=files;return job

def switch_workspace(old,new):
    old,new=Path(old).resolve(),Path(new).resolve()
    if old==new:return new
    if new.is_relative_to(old) or old.is_relative_to(new):raise ValueError('Choose separate workspace folders / 新旧工作目录不能互相嵌套')
    new.mkdir(parents=True,exist_ok=True)
    old_cfg=json.loads((old/'settings.json').read_text('utf-8')) if (old/'settings.json').exists() else {}
    existing=(new/'settings.json').exists()
    cfg=json.loads((new/'settings.json').read_text('utf-8')) if existing else dict(old_cfg)
    if not existing and Path(cfg.get('output',old/'视频作品')).resolve()==(old/'视频作品').resolve():cfg['output']=str(new/'视频作品')
    cfg['history_roots']=unique_roots([*old_cfg.get('history_roots',[]),old_cfg.get('output',str(old/'视频作品')),*cfg.get('history_roots',[]),cfg.get('output',str(new/'视频作品'))])
    for name in ['editing_project.json','enhancer_settings.json','image_settings.json','image_draft.json']:
        src=old/name;dest=new/name
        if src.is_file() and not dest.exists():shutil.copy2(src,dest)
    for name in ['reference_frames','prompt_history','speech_components','generated_images']:
        src=old/name;dest=new/name
        if src.is_dir() and not dest.exists():
            with tempfile.TemporaryDirectory(prefix='.workspace-copy-',dir=new) as staging:
                temp=Path(staging)/name;shutil.copytree(src,temp);os.replace(temp,dest)
    E.atomic_json(new/'settings.json',cfg);remember(new);return new
