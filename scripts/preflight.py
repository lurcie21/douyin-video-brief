"""10 秒内跑完的预检。任一失败立刻退出码 2，并打印「预检失败: ...」。"""
import sys, os, time, subprocess, shutil

t0 = time.time()
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fail(msg):
    print(f"预检失败: {msg}  ({time.time() - t0:.1f}s)")
    sys.exit(2)


def ok(msg):
    print(f"  ok  {msg}")


need_f32 = "--no-f32" not in sys.argv
f32 = os.path.join("tmp-douyin", "audio.f32")
for i, a in enumerate(sys.argv):
    if a == "--f32" and i + 1 < len(sys.argv):
        f32 = sys.argv[i + 1]

print(f"python {sys.version.split()[0]}  {sys.executable}")

try:
    import numpy as np
    import faster_whisper
    import ctranslate2
except Exception as e:
    fail(f"导入失败: {e}")
ok(f"faster_whisper {faster_whisper.__version__} / ctranslate2 {ctranslate2.__version__} / numpy {np.__version__}")

try:
    import av  # noqa: F401
    print("  warn  检测到 av 已安装：本流程不调用它，若哪天走到 decode_audio 会报 metadata_errors")
except Exception:
    ok("av 未安装（预期，走 f32 路径）")

try:
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=12)
    # temperature=0.0 关掉 fallback：纯静音会触发 whisper 的 6 次温度回退，把 2.5s 拖成 15s+
    segs, _ = m.transcribe(np.zeros(16000, dtype=np.float32), language="zh",
                           beam_size=1, temperature=0.0, vad_filter=False,
                           condition_on_previous_text=False)
    list(segs)
    ok("1s 静音转写通过（未走 av 解码）")
except Exception as e:
    fail(f"转写自检失败: {type(e).__name__}: {e}")

if not shutil.which("ffmpeg"):
    fail("ffmpeg 不在 PATH")
ok("ffmpeg 可用")

try:
    r = subprocess.run(["curl", "-sI", "--max-time", "5", "https://hf-mirror.com"],
                       capture_output=True, text=True)
    if "200" not in (r.stdout or ""):
        fail("hf-mirror 无 200 响应（模型下载会失败）")
    ok("hf-mirror 可达")
except FileNotFoundError:
    print("  warn  curl 不可用，跳过镜像检查")

if need_f32:
    if not os.path.exists(f32):
        fail(f"缺少 {f32}（先跑 scripts/assets.py）")
    size = os.path.getsize(f32)
    if size < 16000 * 4:
        fail(f"{f32} 过小（{size} B）")
    ok(f"{f32} 存在（{size / 2**20:.1f} MB ≈ {size / 64000 / 60:.1f} min）")

print(f"预检通过 ({time.time() - t0:.1f}s)")