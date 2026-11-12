# Comfy Video Easy

**English** | [简体中文](README.zh-CN.md)

Our goal is to help people who have never made an AI video—including older adults—get started quickly. With clear labels, reference previews, and a guided interface, users can focus on their ideas without learning the ComfyUI node editor first. A knowledgeable helper still needs to prepare the server and models.

A simple Windows desktop client that turns a ComfyUI MiniMax H3 video workflow into an approachable form. It supports English and Chinese, reference media, two-stage sampling, and local last-frame extraction.

> This client targets a specific MiniMax H3 reference-video workflow. It is not a universal frontend for arbitrary ComfyUI workflows. Install the required models and custom nodes on your own server. This repository contains no model weights, private server addresses, reference media, or generation records.

## Features

- Image, audio, and video references, with image thumbnails and double-click previews.
- Prompts, aspect ratios, and integer durations from 1 to 15 seconds, adjustable with the mouse wheel, arrows, or keyboard.
- First- and second-pass sampling, random or fixed seeds, resolution, and sampling settings.
- Task history, downloads, resumed status checks, saved settings, and refinement.
- In-app video preview with playback controls, an optional system player, and last-frame extraction with FFmpeg.
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

Fixed-choice parameters open a dropdown when clicked; scrolling over a closed selector no longer changes its value. Numeric inputs are unchanged. **Restore default parameters** in Settings resets generation options while preserving the server URL, prompt and references.

Use **Last frame** in the image reference card, then choose **Choose a local file** or **Choose a completed task**. Completed tasks list downloaded videos directly, with date, filename, description and search—no folder browsing is required. Select a video and choose **Extract and add**. Its final frame is saved locally and automatically added as a numbered image reference with a thumbnail. The 9-image limit still applies.

1. Configure the server and check the connection.
2. Add references and refer to them as `<Picture 1>`, `<Audio 1>`, or `<Video 1>`. Reordering changes their numbers.
3. Enter your scene description and dialogue, set duration, aspect ratio, and sampling parameters, then generate.
4. Select a result in **My tasks**. Playback and last-frame extraction are on the right of the task action bar.
5. Choose **Refine this result** to reuse the saved first-pass settings and seed.

You can add up to 9 images, 3 audio clips, and 3 videos. Reference videos must still be 2–15 seconds long. Output duration is aligned to the model's `17k+5` frame grid at 24 fps and may be slightly longer than requested. Durations of 1–4 seconds are below the model's documented usual training range; generation quality at those durations has not been validated. Refinement rebuilds the first- and second-pass API graph rather than loading an internal latent cache from a previous task.

Settings, task records and media paths are kept in the persistent workspace described below. Keep this folder when upgrading. It can contain private prompts, server addresses, and media paths and should not be committed to a public repository.

Each image has an **@** button on its left. Click it to insert its current `<Picture N>` reference at the story cursor. Reordering images updates the buttons’ numbers; existing text is not rewritten.

Use **Set first** beside an image to anchor it at frame 0. Only one image can be selected; click **✓ First** to cancel. Selection follows the file when reordered and clears when removed. The original reference numbering is retained. Both sampling passes use `MiniMaxH3AddGuide`, rebuilt for their own latent resolution. This is model conditioning, not a pasted/replaced frame or a pixel-identical guarantee. Differing aspect ratios are center-cropped. Prompt enhancement receives the selected reference number. The server must provide this node.


Editor preview uses the full sequence duration for seeking, including trimmed source offsets. Clip widths are proportional to their duration; dragging shows the clip under the cursor and an insertion marker. When switching sources, the last decoded image remains visible until the next valid frame arrives, avoiding a black flash; a short loading hold may still occur. Export rendering is unchanged.

## Script prompt enhancement

Choose **Enhance prompt** below the story box. First use opens settings for the API type, URL, API key and exact model name. Later clicks reuse that configuration. Supported request adapters: OpenAI-compatible Chat Completions, OpenAI Responses, Anthropic Messages, Gemini generateContent, and Amazon Bedrock Converse with a Bedrock bearer API key (not AWS access-key signing).

The **Reference format** tab accepts pasted text or imported TXT/Markdown. The bundled neutral format covers references, continuity, duration, shots, sound and negative constraints without importing an example's story. Only the draft, reference format, duration and media counts are sent to your configured endpoint; media files and local paths are not sent. Review and edit the result before applying it. Ctrl+Z restores the previous prompt; originals/results also stay in local `prompt_history`.

The selected generation duration (1–15 seconds) is authoritative, even if the draft or reference example gives another duration. Enhancement instructions require a continuous shot schedule from 0 to the selected duration, with suitable pacing. The review title shows the duration used; changing it while waiting triggers a confirmation before applying.

API keys are encrypted with Windows DPAPI for the current account. They are not included in task manifests or logs; moving settings to another PC/account requires entering the key again. Compatibility Chat endpoints manage their own output cap; other adapters expose a maximum-output setting. Provider/model support varies. Protocol tests use fixtures; real-provider validation requires your own configuration.

Editor playback no longer gates frames or the timeline on exact video-frame timestamps: decoder timestamps can start after zero. Clip transitions are deferred outside decoder callbacks, pending loads retain their seek target, and resuming does not seek the same decoder twice. Regression coverage includes offset timestamps, seek/play, clip boundaries, and split-source playback.

## Character / scene image generation

Choose **Generate character / scene images** in the Images card. In the separate window, write a description and optionally add reference pictures from local files or current video references. First generation asks for an image API type, URL, API key and exact image-model name; later generations reuse this separate configuration. Review the result, enlarge it if needed, then choose **Add to references**. Images are not inserted automatically; the video prompt and first-frame selection remain unchanged.

Supports OpenAI-compatible **Images** endpoints (JSON `/images/generations`; multipart `/images/edits` with references) and Gemini `generateContent` image output. These are image protocols, not arbitrary Chat Completions endpoints. Reference support depends on your model/provider. Request formats follow the [OpenAI image documentation](https://developers.openai.com/api/docs/guides/image-generation) and [Gemini content API](https://ai.google.dev/api/generate-content). A request asks for one image; returned variants can be reviewed. Up to 9 references, at most 25 megapixels per reference and 15 MB total after PNG encoding.

Descriptions and chosen reference image contents are sent to your configured service when you generate. API keys are encrypted with Windows DPAPI in `image_settings.json`, separate from text enhancement. Results stay in `generated_images` in the persistent workspace; the dialog shows the latest 20 images and remembers its draft. Workspace switching copies these settings, drafts and results. Failed requests are not retried automatically. Protocol/UI tests use simulated images; real provider validation requires your own image API configuration.

## Persistent workspace and old tasks

Versions now share a per-user workspace locator in `%LOCALAPPDATA%/ComfyVideoEasy/workspace.json`. A fresh install defaults to `~/Documents/AI视频助手工作区`; an existing portable data folder beside the EXE is adopted when no locator exists. `--data-dir` is an explicit temporary/advanced override and does not change the locator.

In Settings, choose a persistent workspace and a separate video output folder, or restore the workspace's default `视频作品` output. Changing output folders retains old task roots, so previous videos remain in My tasks. **Import old tasks** accepts an old app, data or video-output folder containing task manifests. Copied task folders can resolve downloaded files next to their manifests.

Changing workspace copies settings, drafts and support files without overwriting existing destination configuration. Existing videos remain in their previous folders and stay linked in history: do not delete those folders. Keep the workspace across upgrades; only replace the executable. Settings, prompts, protected credentials and media remain private and are excluded from Git.

## Simple video editor

Open **Video editor** in the sidebar. Add multiple completed task videos or local files. Click the timeline to select a clip and position the playhead; drag clips left or right to reorder them. Set In/Out points and apply the trim, or split at the playhead. Remove unwanted parts and use Undo when needed. The draft saves automatically in `editing_project.json` under your data folder. Original videos are never modified.

Preview plays the trimmed sequence. Export MP4 at 720p/1080p in landscape or portrait; differing aspect ratios are fitted with padding. Export normalizes to 30 fps, H.264 video and AAC audio, adding silence for clips without audio. Processing can be cancelled; an existing output is only replaced after successful completion.

**Auto captions** runs locally with the optional Whisper.cpp v1.8.2 CPU component and multilingual base model. First use offers a roughly 160 MB download from official GitHub/Hugging Face sources, verified with SHA-256. After setup, media stays local. Recognition can be inaccurate: review the text in Edit captions. You can also import SRT or enter captions manually. Export can burn captions into the picture or include a selectable subtitle track. Trimming, splitting or reordering clears existing captions to prevent stale timing; generate captions after arranging your clips.

This is a single-track editor, not a full replacement for a professional NLE: no layered tracks, transitions or complex audio mixing. The Windows multimedia backend handles preview; unsupported source codecs may require conversion. **My tasks** now refreshes the paused preview automatically when the task or result file changes.

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
python -m unittest test_modern test_engine test_editing test_enhancer test_workspaces test_images -v
```

Offline tests use a minimal node fixture with private server enumerations removed. They do not establish compatibility with every live-server version and do not submit GPU jobs.

```powershell
python modern_app.py --self-test test_artifacts/self_test
```

The self-test requires FFmpeg and FFprobe. Add `--check-server` to check the default local server; the ordinary self-test does not connect to a server.

## License

Application source: **GPL-3.0-only**, see [LICENSE](LICENSE). Third-party software and model weights retain their own licenses. See [THIRD_PARTY.md](THIRD_PARTY.md).
