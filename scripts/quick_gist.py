"""快稿通道：SenseVoiceSmall int8（sherpa-onnx，12 线程）+ ffmpeg 静音切分。
产出 gist.txt；术语命中低于阈值时标注「快稿，术语未校」。"""
import argparse, os, re, subprocess, sys, time, wave
import numpy as np
import sherpa_onnx

SR = 16000


def read_wav(path):
    with wave.open(path, "rb") as w:
        total = w.getnframes() / w.getframerate()
        data = w.readframes(w.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0, total


def speech_spans(wav, noise="-32dB", silence=0.30, maxlen=22.0):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav,
                        "-af", f"silencedetect=noise={noise}:d={silence}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = p.stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    total = 0.0
    for m in re.finditer(r"time=(\d+):(\d+):([\d.]+)", log):
        total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    spans, cur = [], 0.0
    for s in starts:
        if s - cur > 0.25:
            spans.append((cur, s))
        cur = s
    spans.append((cur, total))
    out = []
    for a, b in spans:
        if b - a <= 0:
            continue
        n = max(1, int((b - a) // maxlen) + 1)
        step = (b - a) / n
        out += [(a + i * step, a + (i + 1) * step) for i in range(n)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default=os.path.join("tmp-douyin", "audio.wav"))
    ap.add_argument("--dir", default="tmp-douyin")
    ap.add_argument("--models", default=os.path.join("tmp-douyin", "models", "sensevoice"))
    ap.add_argument("--threads", type=int, default=12)
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import terms

    samples, total = read_wav(a.wav)
    t0 = time.time()
    spans = speech_spans(a.wav)
    t_vad = time.time() - t0
    rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=os.path.join(a.models, "model.int8.onnx"),
        tokens=os.path.join(a.models, "tokens.txt"),
        use_itn=True, debug=False, num_threads=a.threads)
    t1 = time.time()
    lines = []
    for s, e in spans:
        chunk = samples[int(s * SR):int(e * SR)]
        if len(chunk) < SR * 0.2:
            continue
        st = rec.create_stream()
        st.accept_waveform(SR, chunk)
        rec.decode_stream(st)
        txt = terms.fix(st.result.text.strip())
        if txt:
            lines.append((s, txt))
    dt = time.time() - t1 + t_vad

    joined = " ".join(t for _, t in lines)
    hits = terms.keyhits(joined)
    label = "" if sum(hits.values()) >= 10 else "（快稿，术语未校）"
    os.makedirs(a.dir, exist_ok=True)
    out = os.path.join(a.dir, "gist.txt")
    with open(out, "w", encoding="utf-8") as f:
        if label:
            f.write(f"# {label}\n")
        for s, t in lines:
            f.write(f"[{s:7.1f}] {t}\n")
    print(f"GIST {dt:.1f}s rtf={dt / total:.3f} spans={len(spans)} lines={len(lines)} "
          f"keyhits={sum(hits.values())} {label} -> {out}")


if __name__ == "__main__":
    main()