---
name: douyin-video-brief
description: 用户发来抖音/小红书/视频号链接要求提炼观点、做笔记或转文稿时使用；内部走取流→音轨→转写→章节卡→结构化五步。
---

# 短视频 → 结构化分析（取流 → 音轨 → 转写 → 章节卡 → 结构化）

目标：一条 15 分钟的口播视频，**6~7 分钟内**产出可引用的逐字稿 + SRT + JSON + 骨架分析；
token 消耗控制在 5 K 以内（两段式：先章节卡骨架，再按章取切片）。

## 0. 环境契约（实测可用组合，不要升级/降级）

| 项 | 值 |
|---|---|
| 解释器 | 由 `scripts/env.sh` 解析：`scripts/env.local.sh`（本机覆盖，不入库）→ `VIDEO_PY`/`PY` 环境变量 → 技能目录下 `.venv/`（Windows 用 `.venv/Scripts/python.exe`）→ PATH 的 `python`。**绝不** pip install 到系统 Python |
| 转写 | `faster-whisper==1.2.1` + `ctranslate2==4.9.0` + `numpy==2.5.5` |
| **不要装 av** | 解码走 `ffmpeg -f f32le` + `numpy.fromfile`，绕开 faster-whisper 1.2.1 与 PyAV 19.x 的 `metadata_errors` 冲突 |
| 快稿通道 | `sherpa-onnx==2.0.2` + `sherpa-onnx-core==2.0.2`（SenseVoiceSmall int8，12 线程） |
| pip 源 | 一律加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`（默认源实测卡 10 分钟） |
| 模型镜像 | `export HF_ENDPOINT=https://hf-mirror.com`（skill 里每次显式 echo 一次） |
| 线程 | `cpu_threads=12` / `num_threads=12`（按本机核数给；8 核以下减半，别超物理核数） |

## 1. 五步流程

### 步骤 0：preflight（必须 ≤10 s，失败立刻停）
```bash
bash ~/.agents/skills/douyin-video-brief/scripts/env.sh '"$PY" ~/.agents/skills/douyin-video-brief/scripts/preflight.py --no-f32'
```
检查四件事，任一失败立刻报「预检失败」并停止（**不要把错误留到 5 分钟后再炸**）：
1. `import faster_whisper, ctranslate2` 可导入
2. 1 秒静音数组跑一次 `model.transcribe(...)`，确认**不走 av 解码**（走 f32 路径）
3. `ffmpeg -version` 与 `curl -sI https://hf-mirror.com` 通
4. 直链返回里有 `play_addr`（取流阶段用）

### 步骤 1：取流（页内 API 主路径，~50 s）
```bash
# A. 已有直链（agent 用浏览器 eval fetch 拿到）：
"$PY" scripts/fetch.py --play-url "<url>" --out tmp-douyin/video.mp4
# B. 直链拿不到时兜底（需要浏览器已登录抖音，cookie 有暴露风险）：
"$PY" scripts/fetch.py --url "<分享链接>" --out tmp-douyin/video.mp4
```
主路径（agent 操作）：`dsh_browser_open` 打开分享链接 → `dsh_browser_execute` 在页内
`fetch("https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id=<id>&pc_client_type=1&version_code=170400&version_name=17.4.0&cookie_enabled=true&platform=PC&downlink=10",{credentials:'include'})`
→ 取 `aweme_detail.video.play_addr.url_list[0]`。
**不要**用抖音 PC 客户端取流（实测无 mp4/m4s 落盘）；**不要**抓 blob/MSE。

### 步骤 2：素材（一次 ffmpeg，~35 s）
```bash
"$PY" scripts/assets.py --video tmp-douyin/video.mp4 --dir tmp-douyin
```
产出 `audio.wav`（16k 单声道）、`audio.f32`（喂转写，不产生 av 解码）、
`sheet01.jpg`（12 帧拼图，找章节卡用）、`key/t<秒>.jpg`（候选章节卡）。

### 步骤 3：转写（small + batch8 + 术语 prompt，~3.8 min）
```bash
"$PY" scripts/transcribe.py --f32 tmp-douyin/audio.f32 --dir tmp-douyin
```
参数固定：`WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=12)` +
`BatchedInferencePipeline(batch_size=8, beam_size=3, vad_filter=True, condition_on_previous_text=False)` +
`initial_prompt=TERMS_GLOSSARY`。
**实测对比**：medium 单条 RTF 0.773（692 s）；medium batch8 0.589（527 s）；
**small+batch8+prompt RTF 0.257（229 s）**，术语命中 25 vs 无 prompt 的 3。
脚本会把 batch 合并的长段按标点回切成字幕级 cue（本次 311 条，最长 49 字、中位 24 字），
所以 SRT 仍然是可用的句级字幕，不会出现 20 多秒一条。

### 步骤 4：术语后处理（秒级）
`scripts/terms.py` 已内置校正表，随转写自动执行；新增术语往 `TERM_FIXES` 里加一行即可。

### 步骤 5：结构化（两段式，token ≤5 K）
1. 先只读 `sheet01.jpg` + 6 张章节卡 → 出六章骨架（~1.5 K token）；
2. 再按章回读 `transcript.txt` 的切片（每章 ~40 行），不全文灌入。
```bash
"$PY" scripts/slice.py --dir tmp-douyin --at 54,270,369,471,597,725   # 默认每章 22 行
```
**实测 token**：骨架阶段 5 781 字符 ≈ 3 854 token + 拼图 ~1.1 K ≈ **4 954 token**（≤5 K 达标）；
要细节时再单独 `--at <某一章> --lines 40`，不要一次把六章都加到 40 行。

一条命令跑完（含预检）：
```bash
bash ~/.agents/skills/douyin-video-brief/scripts/run_all.sh --play-url "<直链>"
```

### 可选：快稿通道（~33 s，术语未校）
```bash
"$PY" scripts/quick_gist.py --wav tmp-douyin/audio.wav --dir tmp-douyin
```
SenseVoiceSmall 出中文骨架快稿；**命中率低于阈值时必须标注「快稿，术语未校」**，
不得当作可引用文稿。

## 2. 产物契约（不要改格式）

| 文件 | 格式 | 说明 |
|---|---|---|
| `transcript.txt` | `[  123.4] 文本` 每行一句 | 下游按行切片依赖此格式 |
| `transcript.srt` | 标准 SRT | 编号 + 时间码 |
| `transcript.json` | `[{"start","end","text"}]` | 机器可读 |
| `key/t<秒>.jpg` | 6 张章节卡 | 帧名带秒数，便于回查 |

## 3. 失败排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `TypeError: open() got an unexpected keyword argument 'metadata_errors'` | 误装了 av | 卸载 av，走 f32 路径（本 skill 默认就是） |
| `uv`/`pip` 装包卡住 >2 min | 用了默认 PyPI | 加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 模型下载慢/失败 | 没走镜像 | `export HF_ENDPOINT=https://hf-mirror.com` |
| `Fresh cookies` | yt-dlp 无登录态 | 走页内 API 主路径，或 `--cookies-from-browser edge`（标注风险） |
| 取流拿不到 `play_addr` | 页面未登录 / 接口字段变更 | 提示用户登录浏览器后重试；不要绕风控 |
| 转写术语全错 | 用了 SenseVoice 快稿 | 快稿仅作骨架，可引用稿必须跑步骤 3 |

## 4. 实测基线（2026-11-21，无独显笔记本 CPU int8，12 线程，899 s 视频）

| 环节 | 改造前 | 现在 | 说明 |
|---|---|---|---|
| 取流 | 3.5 min（先撞 yt-dlp 失败再绕） | **13.6 s** | 页内 API 拿直链，52 MB |
| 素材 | 2 min | **11.5 s** | 单次 ffmpeg 出 wav+f32+拼图+章节卡 |
| 转写 | 707 s（+5 min 返工） | **229 s** | small+batch8+prompt，keyhits 25 |
| 快稿 | — | **42 s** | SenseVoice，48 段，命中 8 → 自动标「术语未校」 |
| 结构化 | ~9 K token | **≈4.95 K token** | 拼图 1 张 + 6 章 × 22 行 |
| **合计** | **≈25.5 min** | **≈5.2 min**（不含最终写作） | 4.9× |

已知代价：small 在 densest 段（450–600 s）中文密度比 medium 低约 25%，
要写「逐句引文」时用 `--at <该章> --lines 40` 回读并人工核对一次。