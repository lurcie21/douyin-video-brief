#!/usr/bin/env bash
# 统一环境入口：所有脚本都用这里解析出的 $PY 起的 Python，不要在系统 Python 里装包。
#
# 解释器查找顺序（先到先用）：
#   1. scripts/env.local.sh 里写死的 PY（本机覆盖，已 gitignore，不随仓库发布）
#   2. 环境变量 VIDEO_PY / PY
#   3. 技能目录下的 .venv（Windows: .venv/Scripts/python.exe，macOS/Linux: .venv/bin/python）
#   4. PATH 里的 python
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$HERE/.." && pwd)"

[ -f "$HERE/env.local.sh" ] && . "$HERE/env.local.sh"

if [ -z "${PY:-}" ]; then
  if [ -n "${VIDEO_PY:-}" ]; then
    PY="$VIDEO_PY"
  elif [ -x "$SKILL_DIR/.venv/Scripts/python.exe" ]; then
    PY="$SKILL_DIR/.venv/Scripts/python.exe"
  elif [ -x "$SKILL_DIR/.venv/bin/python" ]; then
    PY="$SKILL_DIR/.venv/bin/python"
  else
    PY="python"
  fi
fi

export PY
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
# 线程数：默认 12（18 逻辑核时的实测最优），核数更少时取核数；可用 OMP_NUM_THREADS 覆盖
if [ -z "${OMP_NUM_THREADS:-}" ]; then
  _n="$(nproc 2>/dev/null || echo "${NUMBER_OF_PROCESSORS:-8}")"
  if [ "$_n" -lt 12 ] 2>/dev/null; then OMP_NUM_THREADS="$_n"; else OMP_NUM_THREADS="12"; fi
fi
export OMP_NUM_THREADS
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

echo "PY=$PY"
echo "HF_ENDPOINT=$HF_ENDPOINT"
echo "OMP_NUM_THREADS=$OMP_NUM_THREADS"

# 被 run_all.sh 等脚本 source 时：只导出变量，不 exec（否则会顶掉调用方的 shell）
if [ "${BASH_SOURCE[0]}" != "$0" ]; then
  return 0 2>/dev/null || true
fi

# 作为 wrapper 用：bash env.sh <命令> [参数…]
# 也接受一整条命令串：bash env.sh "printenv PY"
if [ "$#" -eq 1 ]; then
  case "$1" in
    *" "*|*"$"*) exec bash -c "$1" ;;
  esac
fi

exec "$@"