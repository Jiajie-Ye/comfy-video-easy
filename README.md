# Comfy Video Easy

**English** | [简体中文](README.zh-CN.md)

A simple Windows desktop client that turns a ComfyUI MiniMax H3 video workflow into an approachable form. It supports English and Chinese, reference media, two-stage sampling, and local last-frame extraction.

> This client targets a specific MiniMax H3 reference-video workflow. It is not a universal frontend for arbitrary ComfyUI workflows. Install the required models and custom nodes on your own server. This repository contains no model weights, private server addresses, reference media, or generation records.

## Features

- Image, audio, and video references, with image thumbnails and double-click previews.
- Prompts, aspect ratios, and integer durations from 1 to 15 seconds, adjustable with the mouse wheel, arrows, or keyboard.
- First- and second-pass sampling, random or fixed seeds, resolution, and sampling settings.
- Task history, downloads, resumed status checks, saved settings, and refinement.
- Local video playback and last-frame extraction with FFmpeg.
- A light interface with rounded controls. Switch languages at the top right or press Alt+L.

## Requirements and setup

Target environment: Windows 10 / 11 x64 and Python 3.11. Validation was performed on the development computer and the GitHub Windows runner, not every Windows version.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python modern_app.py
```

Add FFmpeg and FFprobe to PATH for reference-video inspection and last-frame extraction. Open **Settings** and enter your own ComfyUI URL. The default is `http://127.0.0.1:8188`; reachable LAN and Tailscale addresses also work.

The client needs access to `/system_stats`, `/object_info`, `/upload/image`, `/prompt`, `/queue`, `/history`, and `/view`. There is currently no login or API-token input interface. Use a trusted local or private network connection. Do not expose a ComfyUI server without access controls directly to the public internet.

## Server configuration

Edit `profile.json` to match the model, CLIP, VAE, and LoRA filenames on your server. This is a public example configuration; it does not contain the models. Restart after editing. Packaged applications need to be rebuilt to include changes.

In addition to ComfyUI's core sampling nodes, the workflow uses:

- `MiniMaxH3ReferenceToVideo` and model loaders with MiniMax support.
- `ResolutionSelector`.
- `LayerUtility: ImageScaleByAspectRatio V2`.
- `VHS_LoadVideo` and `VHS_VideoCombine`.
- `ImageResizeKJv2`.
- `PT_H3ConcatAVLatent`.

Server node versions must support the input definitions in `engine.py`. **Check connection** checks model filenames and node availability; the API graph is also validated when a task runs. Obtain and use models and nodes under their respective licenses.

## Usage

1. Configure the server and check the connection.
2. Add references and refer to them as `<Picture 1>`, `<Audio 1>`, or `<Video 1>`. Reordering changes their numbers.
3. Enter your scene description and dialogue, set duration, aspect ratio, and sampling parameters, then generate.
4. Select a result in **My tasks**. Playback and last-frame extraction are on the right of the task action bar.
5. Choose **Refine this result** to reuse the saved first-pass settings and seed.

You can add up to 9 images, 3 audio clips, and 3 videos. Reference videos must still be 2–15 seconds long. Output duration is aligned to the model's `17k+5` frame grid at 24 fps and may be slightly longer than requested. Durations of 1–4 seconds are below the model's documented usual training range; generation quality at those durations has not been validated. Refinement rebuilds the first- and second-pass API graph rather than loading an internal latent cache from a previous task.

Settings, task records, and media paths are saved in the `我的视频数据` folder beside the application. Use `--data-dir` to choose another location. Keep this folder when upgrading. It can contain private prompts, server addresses, and media paths and should not be committed to a public repository.

## Build a Windows EXE

```powershell
pip install -r requirements-dev.txt
$env:CVE_FFMPEG_DIR = 'C:\tools\ffmpeg\bin'
python build_exe.py
```

The directory must contain `ffmpeg.exe`, `ffprobe.exe`, and their required DLLs. The output is `dist/AI视频助手.exe`. The build script does not download third-party binaries. When distributing a build, include the licenses and source information required by the selected FFmpeg build, Qt/PyQt, and other bundled components.

## Testing

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest test_modern test_engine -v
```

Offline tests use a minimal node fixture with private server enumerations removed. They do not establish compatibility with every live-server version and do not submit GPU jobs.

```powershell
python modern_app.py --self-test test_artifacts/self_test
```

The self-test requires FFmpeg and FFprobe. Add `--check-server` to check the default local server; the ordinary self-test does not connect to a server.

## License

Application source: **GPL-3.0-only**, see [LICENSE](LICENSE). Third-party software and model weights retain their own licenses. See [THIRD_PARTY.md](THIRD_PARTY.md).
