# Third-party components

No third-party binaries or model weights are committed in this repository.

- Python: Python Software Foundation License — https://docs.python.org/3/license.html
- PyQt6: GPL v3 or commercial license; this project uses the GPL version — https://www.riverbankcomputing.com/software/pyqt/
- Qt: module-specific LGPL/GPL/commercial licenses — https://www.qt.io/licensing/
- Requests: Apache-2.0 — https://github.com/psf/requests
- Requests transitive dependencies retain their respective licenses.
- PyInstaller: GPL with its bootloader distribution exception — https://pyinstaller.org/en/stable/license.html
- FFmpeg / FFprobe: license depends on the chosen build and enabled components — https://ffmpeg.org/legal.html

Builds that bundle FFmpeg, Qt or other dependencies must preserve notices and meet the corresponding source-distribution and other applicable license requirements. The application GPL license does not relicense model weights, custom nodes, media inputs or generated content.

Optional speech recognition is downloaded separately on request: [Whisper.cpp v1.8.2](https://github.com/ggml-org/whisper.cpp/tree/v1.8.2), MIT license, and the [Whisper multilingual base model](https://huggingface.co/ggerganov/whisper.cpp), distributed under its own model/license terms. Downloads are pinned by SHA-256 in edit_engine.py. These files are not committed or bundled in the application ZIP.
