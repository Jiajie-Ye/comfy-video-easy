# Comfy Video Easy · AI 视频助手

[English](README.md) | **简体中文**

简洁的 Windows 桌面客户端，将 ComfyUI MiniMax H3 视频工作流整理成易用的表单。支持中文 / English、参考素材、两阶段采样及本地末帧提取。

> 本项目适配特定 MiniMax H3 参考视频工作流，不是任意 ComfyUI 工作流的通用前端。模型和自定义节点需要用户自行在服务器安装；仓库不包含模型权重、私人服务器地址、素材或生成记录。

## 功能

- 图片、音频、视频参考素材；图片缩略图和双击预览。
- Prompt、画面比例、1–15 秒整数时长；鼠标滚轮、箭头和键盘输入。
- 一采 / 二采、随机或固定种子、分辨率和采样参数。
- 任务记录、下载、恢复查询、载入参数和继续二采。
- 本地播放、FFmpeg 提取最后一帧。
- 浅色圆角界面；右上角切换中英文，快捷键 Alt+L。

## 环境与启动

目标环境：Windows 10 / 11 x64、Python 3.11。已在开发电脑及 GitHub Windows 运行环境验证，未覆盖所有 Windows 版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python modern_app.py
```

将 FFmpeg 和 FFprobe 加入 PATH，供参考视频检测和末帧提取使用。首次启动后进入 **高级设置 / Settings**，填写自己的 ComfyUI URL。默认是 `http://127.0.0.1:8188`，也支持可访问的局域网或 Tailscale 地址。

客户端需要访问 `/system_stats`、`/object_info`、`/upload/image`、`/prompt`、`/queue`、`/history`、`/view`。目前没有登录或 API token 输入界面；它适用于你信任的本地或私有网络连接。不要将未设访问控制的 ComfyUI 直接开放到公网。

## 配置服务器

编辑 `profile.json`，让模型、CLIP、VAE、LoRA 文件名与服务器一致。该文件是公开示例配置，不包含模型本身。修改后重启；打包版本需重新构建。

除 ComfyUI 核心采样节点外，此工作流使用：

- `MiniMaxH3ReferenceToVideo` 及支持 MiniMax 的模型加载器。
- `ResolutionSelector`。
- `LayerUtility: ImageScaleByAspectRatio V2`。
- `VHS_LoadVideo`、`VHS_VideoCombine`。
- `ImageResizeKJv2`。
- `PT_H3ConcatAVLatent`。

服务器节点版本必须兼容 `engine.py` 中的输入定义。点击“检查连接”会检查模型文件名和节点是否存在；运行时还会校验 API 图。模型和节点按各自许可证获取、使用。

## 使用

1. 配置服务器，检查连接。
2. 添加素材，按 `<Picture 1>`、`<Audio 1>`、`<Video 1>` 引用。排序会改变编号。
3. 写入画面描述与对白，设置时长、比例和采样参数，开始生成。
4. 在“我的任务”选择结果；右侧可播放或提取末帧。
5. 满意后选择“用这条做二采”，复用保存的一采参数和种子。

图片最多 9 张，音频和视频各 3 段；参考视频仍要求 2–15 秒。输出时长按模型的 `17k+5` 帧网格、24 fps 对齐，可能略长于设置值。1–4 秒短于模型标注的常用训练范围，生成质量未验证。二采操作会重建一采及二采 API 图，并非读取先前任务的内部 latent 缓存。

任务、设置和素材路径保存在程序旁的“我的视频数据”文件夹；可用 `--data-dir` 指定其他位置。升级时保留该文件夹。它可能含私人 Prompt、服务器地址和素材路径，不应提交到公开仓库。

## 构建 EXE

```powershell
pip install -r requirements-dev.txt
$env:CVE_FFMPEG_DIR = 'C:\tools\ffmpeg\bin'
python build_exe.py
```

目录须包含 `ffmpeg.exe`、`ffprobe.exe` 及其依赖 DLL。输出为 `dist/AI视频助手.exe`。构建脚本不会下载第三方二进制；分发时需附带所选 FFmpeg 构建及 Qt/PyQt 等组件要求的许可证和源码说明。

## 测试

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest test_modern test_engine -v
```

离线测试使用最小、去除服务器枚举的节点 fixture，不代表真实服务器所有版本的兼容性，也不会提交 GPU 任务。

```powershell
python modern_app.py --self-test test_artifacts/self_test
```

自检需要 FFmpeg / FFprobe。可另加 `--check-server` 检查默认本地服务器；普通自检不连接服务器。

## 许可证

应用源码采用 **GPL-3.0-only**，详见 [LICENSE](LICENSE)。第三方软件和模型权重保留各自的许可证。详见 [第三方组件说明](THIRD_PARTY.md)。
