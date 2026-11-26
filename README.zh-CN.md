> 我们的人生就像一池时间。时间不断流走，水位也随之下降。带着这个想法，我做了「时间池」，用来看看哪些时间悄悄流走了，也为未来的计划分配时间。

# 时间池

[English](README.md) · **简体中文**

时间池是一款桌面时间记录工具，数据保存在本机。你可以手动记录活动，也可以用英语或普通话口述一天的安排，再按分类回顾从一天到一年的时间分配。这个项目的灵感来自 2026 年春天的一个清晨，那时我正在读九年级，备战中考。

## Windows 快速开始

**Windows x64 · 单文件运行 · 无需 Python 或 Conda**

在 GitHub 发布页的 **Assets** 中下载 `TimePool.exe`，双击即可运行。从源码打包的文件位于 `dist/TimePool.exe`。手动记录不需要安装程序、账号、API 密钥或语音模型。

想先用样例试试？在 EXE 所在目录打开 PowerShell：

```powershell
.\TimePool.exe --demo
```

试用包含六周样例记录。试用数据和设置与正式档案隔离，正常退出后会清理。界面默认是英语，可通过侧栏的 **Interface language** 切换为简体中文。

## 记录和回顾

- 按大类和小类新增、编辑、删除或补记活动。时长以整数分钟保存，每天累计不得超过 24 小时。
- 按日、周、月、季度或年查看汇总。支持柱状图、饼图，也可以点击分类查看小类分布。
- 查看未分配时间。过去日期显示为 `timeleak`，根据已记录时长计算，不作为记录单独保存。

## 口述录入

1. 在 **AI 快速录入** 中点击 **下载语音模型**。英语和普通话共用一份 [Whisper Base](https://huggingface.co/Systran/faster-whisper-base) 模型，约 148 MB，不包含在 EXE 中。
2. 选择 **自动检测**、**英语** 或 **普通话**，点击 **本地麦克风录音**。每段最多两分钟，说完点 **停止并转写**。
3. 检查并编辑转写文本。要生成带日期的时间记录，先在 **设置** 中配置 LLM，再点 **LLM 整理预览**，核对后写入。

模型下载后，麦克风转写可在 CPU 上离线运行。录音只留在内存中，不会上传。将文本发给 LLM 是单独的可选操作。

| 可选服务 | 用途 |
| --- | --- |
| **LLM** | 通过 OpenAI 兼容的 `/chat/completions` 接口，从文本中提取活动、日期和时长。 |
| **文件 STT** | 将选中的音频文件发送至 OpenAI 兼容的 `/audio/transcriptions` 接口。 |
| **外部实时 STT** | 从你运行或配置的 WebSocket 服务接收转写文本，不调用麦克风。 |

程序不会启动外部服务。外部实时 STT 连接失败不影响本地录音。如果打不开麦克风，请检查 Windows 的默认输入设备和桌面应用麦克风权限。

## 数据与隐私

EXE 使用 `%LOCALAPPDATA%\Time Pool` 存放数据，源码版则使用项目目录。EXE 不会自动导入源码版的记录或设置。

| 文件或目录 | 内容 |
| --- | --- |
| `time_pool_data.json` | 活动记录 |
| `time_pool_settings.json` | 界面偏好和 API 配置 |
| `backup/` | 完整数据备份，每天最多一次，在启动时检测到跨日或当天首次更改记录前触发 |
| `.timepool_models/` | 已下载的语音模型 |

这些文件不会进入 Git。直接填入设置的 API 密钥会以明文保存；也可以通过环境变量提供密钥。暂不支持多设备同步。

## 从源码运行或构建

Windows 上使用 Conda 时，先运行一次 [`prepare_anaconda_env.bat`](prepare_anaconda_env.bat)，再用 [`try_timepool.bat`](try_timepool.bat) 试用样例，或用 [`run_timepool.bat`](run_timepool.bat) 正式运行。安装失败可查看 `prepare_anaconda_env.log`。

也可以在已激活的 Windows x64 Python 3.12 环境中，从项目根目录运行或构建：

```powershell
# 从源码运行
python -m pip install -r requirements.txt
python main.py --demo
python -m unittest discover -s tests

# 构建独立 EXE
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm TimePool.spec
```

[打包配置](TimePool.spec) 会生成 `dist/TimePool.exe`。发布到 GitHub 时，把 EXE 和可选的 SHA-256 校验文件作为 Release 附件上传，不要把 `dist/` 提交进仓库。

时间池使用 PySide6 构建桌面界面、Matplotlib 绘制图表，以及 faster-whisper 进行离线转写。
