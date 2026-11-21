# douyin-video-brief

**把一条抖音（或小红书 / 视频号）链接，变成可引用的逐字稿 + 字幕 + 骨架分析：从取流到出稿，机器侧约 5 分钟。**

这是一个给 AI Agent 用的**技能包**（skill）：`SKILL.md` 告诉 Agent 什么时候用、按什么顺序做，
`scripts/` 里的 9 个脚本把「取视频 → 抽音轨/章节卡 → 语音转写 → 结构化分析」每一步都做成可直接执行的命令。

---

## 一句话简介

> 发我一条抖音链接，我给你一份能引用的文字稿，顺带告诉你这条视频讲了什么。

---

## 用途与适用场景

适合下面这些时刻：

- 用户发来一条**抖音 / 小红书 / 视频号链接**，说「这视频讲了啥」「帮我提炼观点」「做个笔记」「转成文字」；
- 想把一条 10–30 分钟的口播/访谈视频，变成**带时间码的逐字稿**，方便引用原话；
- 想同时拿到**字幕文件（SRT）**，拿去压进视频或做成笔记；
- 想先快速看个**骨架**（章节 + 每章要点），再决定要不要细读全文。

不适合：需要绕过平台风控/验证码/付费墙的内容；需要逐帧分析画面（本流程只抽样章节卡）；
对术语准确度要求极高又不接受人工复核的场合（见「已知代价」）。

---

## 安装与依赖

### 1. 准备一个独立的虚拟环境

**不要**把依赖装进系统 Python。

```bash
# Windows（bash / Git Bash / MSYS）
python -m venv .venv
.venv/Scripts/python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  faster-whisper==1.2.1 ctranslate2==4.9.0 numpy==2.5.5 sherpa-onnx==2.0.2

# macOS / Linux
python -m venv .venv
.venv/bin/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  faster-whisper==1.2.1 ctranslate2==4.9.0 numpy==2.5.5 sherpa-onnx==2.0.2
```

锁死这三个版本是实测过的组合，别随手升级：

| 包 | 版本 | 作用 |
|---|---|---|
| `faster-whisper` | `1.2.1` | 主力转写（CTranslate2 后端，CPU int8 可跑） |
| `ctranslate2` | `4.9.0` | faster-whisper 的推理引擎 |
| `numpy` | `2.5.5` | 音频以 `float32` 数组直接喂给模型 |
| `sherpa-onnx` | `2.0.2` | 仅「快稿通道」用（SenseVoiceSmall），可选 |

### 2. 关于 `av`：**不要靠它解码**

`faster-whisper 1.2.1` 的 `decode_audio()` 会给 `av.open()` 传 `metadata_errors` 参数，
而 `PyAV 19.x` 已经删掉了这个参数，于是报：

```
TypeError: open() got an unexpected keyword argument 'metadata_errors'
```

**本流程完全不调用这条路径**：音轨先用 `ffmpeg -f f32le` 解成裸 float32，
再用 `numpy.fromfile()` 读进内存交给 `model.transcribe()`。

`av` 可能作为 `faster-whisper` 的依赖被顺带装上——**装了就装了，别去升/降它的版本**，
预检脚本只会打一行 `warn` 提示，不影响运行。

### 3. 系统依赖

- `ffmpeg`（必需，解音轨 / 抽帧 / 静音切分）
- `bash`（脚本是 POSIX shell；Windows 用 Git Bash / MSYS）
- 可选：`curl`（预检验证镜像可达）

### 4. 告诉脚本用哪个 Python

三种方式，任选其一（优先级从高到低）：

```bash
# A. 本机覆盖文件（推荐；已 gitignore，不会误提交）
cp scripts/env.local.sh.example scripts/env.local.sh
#   然后编辑 scripts/env.local.sh，把 PY 改成你的解释器绝对路径

# B. 环境变量
export VIDEO_PY="/path/to/.venv/Scripts/python.exe"     # Windows
export VIDEO_PY="/path/to/.venv/bin/python"             # macOS/Linux

# C. 把 venv 放在技能目录下的 .venv/（脚本会自动发现）
```

### 5. 模型从哪里来

- **Whisper 模型**（`small` 默认）：首次运行自动下载，缓存在 `~/.cache/huggingface/hub`。
  国内网络请确保 `HF_ENDPOINT=https://hf-mirror.com`（`env.sh` 已默认设置）。
- **SenseVoiceSmall**（快稿通道，约 239 MB）：手动放好即可，缺了只是 `--no-gist` 不出快稿。

```bash
BASE=https://hf-mirror.com/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main
mkdir -p tmp-douyin/models/sensevoice
curl -L -o tmp-douyin/models/sensevoice/model.int8.onnx "$BASE/model.int8.onnx"
curl -L -o tmp-douyin/models/sensevoice/tokens.txt      "$BASE/tokens.txt"
```

---

## 快速开始

### 一条命令跑完

```bash
cd <一个有写权限的工作目录>          # 产物会落在 ./tmp-douyin/
bash /path/to/douyin-video-brief/scripts/run_all.sh --play-url "<视频直链>"
```

跑完得到：

```
tmp-douyin/
├── video.mp4              视频
├── audio.wav / audio.f32  音轨（16 kHz 单声道 / 裸 float32）
├── transcript.txt         逐字稿，`[  123.4] 文本` 一行一句
├── transcript.srt         字幕级 cue（按标点切，长句 ≤ 50 字）
├── transcript.json        结构化分段（start/end/text）
├── gist.txt               快稿（SenseVoice，术语未校时首行会标注）
├── sheet01.jpg            章节卡拼图（一眼看结构）
└── key/t<秒>.jpg          章节卡原图
```

### 怎么拿到 `<视频直链>`

主路径（推荐，不需要 cookie）：

1. 在浏览器里打开分享短链（如 `https://v.douyin.com/xxxx/`），等它跳到 `www.douyin.com/video/<id>`；
2. 在该页面控制台里发一条同源请求拿播放地址：

```js
fetch("https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web"
      + "&aweme_id=<视频ID>&pc_client_type=1&version_code=170400&version_name=17.4.0"
      + "&cookie_enabled=true&platform=PC&downlink=10", {credentials: "include"})
  .then(r => r.json())
  .then(d => console.log(d.aweme_detail.video.play_addr.url_list[0]));
```

3. 拿到的是**带时效签名的直链**（`*.douyinvod.com`，含 `dy_q` / `l=` 参数），尽快下载，过期重取。

兜底（yt-dlp，可能会要求登录态）：

```bash
bash scripts/run_all.sh --url "https://v.douyin.com/xxxx/"
bash scripts/run_all.sh --url "https://v.douyin.com/xxxx/" --cookie-browser edge   # 见「风险与合规」
```

### 只跑其中一步

```bash
bash scripts/env.sh "printenv PY"                          # 看解释器解析结果（含 PY/HF_ENDPOINT/线程数）
"$PY" scripts/preflight.py --no-f32                       # 只预检
"$PY" scripts/fetch.py  --play-url "<直链>" --out tmp-douyin/video.mp4
"$PY" scripts/assets.py --video tmp-douyin/video.mp4 --dir tmp-douyin
"$PY" scripts/transcribe.py --f32 tmp-douyin/audio.f32 --dir tmp-douyin --model small --batch 8
"$PY" scripts/quick_gist.py --wav tmp-douyin/audio.wav --dir tmp-douyin
"$PY" scripts/slice.py --at 54,270,369,471,597,725 --lines 22      # 按章取切片
```

---

## 五步流程与 6 秒预检

| 步骤 | 做什么 | 脚本 | 实测 |
|---|---|---|---|
| **0. 预检** | 导入依赖 / 转 1 秒静音 / 查 ffmpeg / 查镜像 / 查 f32 是否已就绪 | `preflight.py` | **5.9 s** |
| **1. 取流** | 用直链 + UA/Referer 下载；`--url` 时走 yt-dlp 兜底 | `fetch.py` | **13.6 s**（52 MB） |
| **2. 素材** | 一次 ffmpeg 出 `wav` / `f32` / 拼图 / 章节卡 | `assets.py` | **11.5 s** |
| **3. 转写** | `small` + `batch=8` + 术语 prompt → txt/srt/json，按标点回切成字幕 cue | `transcribe.py` | **229 s**（RTF 0.257） |
| **4. 快稿** | SenseVoice 12 线程切分转写，术语命中 <10 自动标注「未校」 | `quick_gist.py` | **42 s** |
| **5. 结构化** | 章节卡拼图（1 张）+ 每章 22 行切片 → 写分析（≤5 K token） | `slice.py` + 人/模型 | 模型侧 |

**为什么要 6 秒预检**：第一次跑最贵的失败是「模型下完 1.5 GB 才报错」。
预检把你的错误提前到 6 秒内——依赖缺、ffmpeg 缺、镜像不通、f32 没生成，都在这儿拦下来。

> 预检里那个「1 秒静音转写」必须带 `temperature=0.0`：否则 whisper 会走 6 次温度回退，
> 把 2.5 秒拖成 15 秒以上。

---

## 实测效果（本机基准，非承诺值）

环境：Windows，Intel Ultra 5 125H（18 逻辑核，**无独显**），12 线程，CPU int8。

| 环节 | 改造前 | 现在 | 说明 |
|---|---|---|---|
| 取流 | 3.5 min（先撞 yt-dlp 失败再绕） | **13.6 s** | 页内 API 拿直链，52 MB |
| 素材 | 2 min | **11.5 s** | 单次 ffmpeg 出全部素材 |
| 转写 | 707 s（另有 5 min 返工） | **229 s** | small + batch8 + 术语 prompt，命中 25 |
| 快稿 | — | **42 s** | SenseVoice，48 段 |
| 结构化 | ~9 K token | **≈4.95 K token** | 1 张拼图 + 6 章 × 22 行 |
| **合计** | **≈25.5 min** | **≈6.5 min** | 机器侧 307 s，**约 4.9×** |

一条 899 秒的视频，转写 **RTF 0.257**（229 秒出 311 条字幕级 cue），
术语命中 **25** 次（`Scaling Law` / `RAG` / `Chinchilla` / `Agentforce` / `CLI-Anything` 等）。

---

## 已知代价

- **快稿是快稿**：SenseVoice 42 秒出稿，但专有名词容易崩（`Scaling Law` → `cal`）。
  命中率不足时首行会自动写 `# （快稿，术语未校）`——**别拿它当可引用的稿子**，它只用来搭骨架。
- **`small` 在密集段落密度偏低**：语速最快的那一段（本机实测 450–600 s），中文密度比 `medium` 低约 25%。
  要写「逐句引文」时，用 `slice.py --at <该章> --lines 40` 回读，并人工核一次。
- **token 数是估算值**：按「中文 1 字符 ≈ 1/1.5 token + 拼图约 1.1 K」估的，不是 tokenizer 实测。
- **单机单进程**：18 线程已经吃满，再加并行只会互相抢核；不要指望多开几个进程变快。
- **直链有时效**：签名 URL 放久了会 403，重取一次即可。

---

## 风险与合规

- 只处理**你有权获取**的公开视频，用于个人学习、笔记、研究；产物版权归原作者，二次发布请先获授权。
- **不绕过平台风控**：不碰验证码、不破解付费/会员内容、不做自动化批量抓取。
- `--cookie-browser` 会把**浏览器登录态（cookie）**交给 yt-dlp，属敏感信息外带，仅在你自己机器上、
  确有必要时使用；脚本会打印风险提示。多数情况下**不需要**它——直链那条路更好。
- 直链来自页面同源请求，使用的是你当前已登录/已访问的会话；不要用它去抓取未获授权的批量内容。
- 遵守抖音/小红书/视频号的服务条款与 `robots` 约定；本项目不对使用者的抓取对象做任何背书。

---

## 目录结构

```
douyin-video-brief/
├── SKILL.md                    给 Agent 看的说明书（何时触发、五步、环境契约、排查）
├── README.md                   给人看的说明书（就是本文件）
├── scripts/
│   ├── env.sh                  解释器/镜像/线程统一解析（wrapper：bash env.sh <cmd>）
│   ├── env.local.sh.example    本机覆盖模板（复制成 env.local.sh 后改 PY）
│   ├── preflight.py            6 秒预检
│   ├── fetch.py                取流（直链优先，yt-dlp 兜底）
│   ├── assets.py               音轨 + 拼图 + 章节卡
│   ├── transcribe.py           转写 → txt/srt/json（含标点回切）
│   ├── terms.py                术语表（prompt + 事后正则校正）
│   ├── quick_gist.py           快稿通道（SenseVoice）
│   ├── slice.py                按章取切片
│   └── run_all.sh              一条命令跑完
└── .gitignore                  忽略 env.local.sh / models/ / tmp-douyin/ / *.onnx / venv
```

## 排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `预检失败: 导入失败` | venv 没装依赖，或 `PY` 指错 | 看 `bash scripts/env.sh "echo $PY"` 的输出 |
| `TypeError: ... metadata_errors` | 走了 `decode_audio`（旧脚本/旧调用） | 用本仓库的 `transcribe.py`，它喂 `numpy` 数组，不碰 av |
| `预检失败: hf-mirror 无 200` | 镜像不通 | 换 `HF_ENDPOINT`，或先手动下模型 |
| 取流 403 | 直链过期 | 回页面重新拿 `play_addr` |
| 字幕一条 20 多秒 | 用了 `batch` 又关掉了回切 | 加 `--no-split` 之外别关；默认会按标点切 |
| 快稿术语全错 | 用了 SenseVoice | 正常；要可引用稿请跑第 3 步 |

## License

MIT（脚本可自由取用；视频内容版权归原作者）。