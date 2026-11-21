"""转写：f32 -> transcript.txt / .srt / .json（格式保持不变）。"""
import argparse, json, os, sys, time
import numpy as np


def fmt_ts(t, sep=","):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def split_cues(text, start, end, max_chars=48):
    """batch 模式会把整段 VAD 块合成一条，这里按标点回切成字幕级 cue，时间按字数比例分配。"""
    import re
    parts = [p for p in re.split(r"(?<=[。！？!?])", text) if p and p.strip()]
    cues = []
    for p in parts:
        if len(p) <= max_chars:
            cues.append(p)
        else:
            cues += [s for s in re.split(r"(?<=[，,；;])", p) if s]
    cues = [c for c in cues if c.strip()]
    # 兜底：整段没标点时（whisper 偶尔不加标点）按 22 字硬切，避免出现 20 多秒一条的字幕
    wrapped = []
    for c in cues:
        if len(c) <= max_chars:
            wrapped.append(c)
        else:
            step = 22
            wrapped += [c[i:i + step] for i in range(0, len(c), step)]
    cues = wrapped
    if not cues:
        return []
    total_chars = sum(len(c) for c in cues)
    span = max(end - start, 0.01)
    out, cur = [], start
    for c in cues:
        d = span * len(c) / total_chars
        out.append({"start": round(cur, 2), "end": round(min(cur + d, end), 2), "text": c.strip()})
        cur += d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f32", default=os.path.join("tmp-douyin", "audio.f32"))
    ap.add_argument("--dir", default="tmp-douyin")
    ap.add_argument("--model", default="small")
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--no-prompt", action="store_true")
    ap.add_argument("--no-split", action="store_true", help="不按标点回切成字幕级 cue")
    a = ap.parse_args()
    if not os.path.exists(a.f32):
        print(f"缺少 {a.f32}", file=sys.stderr)
        sys.exit(2)

    import terms  # 同目录
    from faster_whisper import WhisperModel, BatchedInferencePipeline

    audio = np.fromfile(a.f32, dtype=np.float32)
    secs = len(audio) / 16000
    print(f"audio {len(audio)} samples = {secs:.1f}s  model={a.model} batch={a.batch} threads={a.threads}")

    t0 = time.time()
    m = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=a.threads)
    pipe = BatchedInferencePipeline(model=m)
    segs, info = pipe.transcribe(
        audio, language="zh", batch_size=a.batch, beam_size=3, vad_filter=True,
        initial_prompt=None if a.no_prompt else terms.GLOSSARY,
        condition_on_previous_text=False)
    segs = list(segs)
    dt = time.time() - t0

    rows = []
    for s in segs:
        txt = terms.fix(s.text.strip())
        if not txt:
            continue
        if a.no_split:
            rows.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": txt})
        else:
            rows += split_cues(txt, s.start, s.end)

    os.makedirs(a.dir, exist_ok=True)
    txt_path = os.path.join(a.dir, "transcript.txt")
    srt_path = os.path.join(a.dir, "transcript.srt")
    json_path = os.path.join(a.dir, "transcript.json")
    with open(txt_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(f"[{r['start']:7.1f}] {r['text']}\n")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            f.write(f"{i}\n{fmt_ts(r['start'])} --> {fmt_ts(r['end'])}\n{r['text']}\n\n")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    joined = " ".join(r["text"] for r in rows)
    hits = terms.keyhits(joined)
    print(f"DONE {dt:.1f}s  rtf={dt / secs:.3f}  segs={len(rows)}  chars={len(joined)}  "
          f"keyhits={sum(hits.values())} {hits}")
    print(f"wrote {txt_path} / {srt_path} / {json_path}")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()