#!/usr/bin/env bash
# 一条命令跑完：取流 -> 素材 -> 转写 -> 快稿。用法：
#   bash run_all.sh --play-url "<直链>"          # 主路径（推荐）
#   bash run_all.sh --url "<分享链接>" [--cookie-browser edge]
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
WS="${WS:-$PWD}"
cd "$WS" || exit 1
# 解释器 / 镜像 / 线程数由 env.sh 统一解析（本机覆盖写在 scripts/env.local.sh，不入库）
. "$DIR/env.sh" >/dev/null
THREADS="${OMP_NUM_THREADS:-12}"

PLAY_URL=""; URL=""; COOKIE=""; GIST=1
while [ $# -gt 0 ]; do
  case "$1" in
    --play-url) PLAY_URL="$2"; shift 2;;
    --url) URL="$2"; shift 2;;
    --cookie-browser) COOKIE="$2"; shift 2;;
    --no-gist) GIST=0; shift;;
    *) echo "unknown arg $1"; exit 2;;
  esac
done

T0=$(date +%s)
"$PY" "$DIR/preflight.py" --no-f32 || { echo "预检失败，停止"; exit 2; }

if [ -n "$PLAY_URL" ]; then
  "$PY" "$DIR/fetch.py" --play-url "$PLAY_URL" --out tmp-douyin/video.mp4 || exit 2
else
  "$PY" "$DIR/fetch.py" --url "$URL" ${COOKIE:+--cookie-browser "$COOKIE"} --out tmp-douyin/video.mp4 || exit 2
fi

"$PY" "$DIR/assets.py" --video tmp-douyin/video.mp4 --dir tmp-douyin || exit 2
"$PY" "$DIR/transcribe.py" --f32 tmp-douyin/audio.f32 --dir tmp-douyin --model small --batch 8 --threads "$THREADS" || exit 2
[ "$GIST" = "1" ] && "$PY" "$DIR/quick_gist.py" --wav tmp-douyin/audio.wav --dir tmp-douyin --threads "$THREADS"

echo "总耗时 $(( $(date +%s) - T0 ))s  产物：tmp-douyin/transcript.{txt,srt,json} + key/"