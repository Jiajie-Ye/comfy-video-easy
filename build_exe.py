"""Reproducible PyInstaller single-file build with the full FFmpeg DLL set."""
import os,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ffmpeg_dir=os.environ.get('CVE_FFMPEG_DIR')
if not ffmpeg_dir:raise SystemExit('Set CVE_FFMPEG_DIR to a folder containing ffmpeg.exe, ffprobe.exe and required DLLs.')
FFMPEG=Path(ffmpeg_dir).resolve()
if not (FFMPEG/'ffmpeg.exe').is_file():raise SystemExit('请设置 CVE_FFMPEG_DIR 为包含 ffmpeg.exe、ffprobe.exe 和 DLL 的文件夹。')
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--name','AI视频助手',
      '--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build'),'--specpath',str(ROOT/'build'),
      '--add-data',str(ROOT/'profile.json')+os.pathsep+'.',
      '--add-data',str(ROOT/'prompt_template.txt')+os.pathsep+'.',
      '--add-data',str(ROOT/'check.svg')+os.pathsep+'.',
      '--add-data',str(ROOT/'arrow_up.svg')+os.pathsep+'.',
      '--add-data',str(ROOT/'arrow_down.svg')+os.pathsep+'.',
      '--exclude-module','tkinter',
      '--exclude-module','numpy','--exclude-module','pandas','--exclude-module','matplotlib',
      '--exclude-module','scipy','--exclude-module','torch','--exclude-module','IPython',
      '--exclude-module','pytest','--exclude-module','PyQt5','--exclude-module','PySide6']
for f in [FFMPEG/'ffmpeg.exe',FFMPEG/'ffprobe.exe',*FFMPEG.glob('*.dll')]:args+=['--add-binary',str(f)+os.pathsep+'ffmpeg']
args += [str(ROOT/'modern_app.py')]
subprocess.run(args,check=True,cwd=ROOT)
