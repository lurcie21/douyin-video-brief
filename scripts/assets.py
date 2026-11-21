"""一次 ffmpeg 产出：audio.wav / audio.f32 / sheet01.jpg / key/t*.jpg"""
import argparse, os, subprocess, time


def dur(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", video], capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=os.path.join("tmp-douyin", "video.mp4"))
    ap.add_argument("--dir", default="tmp-douyin")
    ap.add_argument("--sheet", type=int, default=12, help="拼图取样帧数")
    ap.add_argument("--key", type=int, default=6, help="章节卡候选张数")
    a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)
    keydir = os.path.join(a.dir, "key")
    os.makedirs(keydir, exist_ok=True)
    t0 = time.time()
    d = dur(a.video)

    wav = os.path.join(a.dir, "audio.wav")
    f32 = os.path.join(a.dir, "audio.f32")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-vn",
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-vn",
                    "-ac", "1", "-ar", "16000", "-f", "f32le", f32], check=True)

    fps = max(a.sheet / d, 1e-6)
    sheet = os.path.join(a.dir, "sheet01.jpg")
    cols = 4 if a.sheet >= 8 else 3
    rows = (a.sheet + cols - 1) // cols
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video,
                    "-vf", f"fps={fps:.6f},scale=480:-1,tile={cols}x{rows}",
                    "-frames:v", "1", "-q:v", "4", sheet], check=True)

    for i in range(a.key):
        ts = d * (i + 0.5) / a.key
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ts:.3f}",
                        "-i", a.video, "-frames:v", "1", "-vf", "scale=720:-1",
                        "-q:v", "4", os.path.join(keydir, f"t{int(ts)}.jpg")], check=True)

    print(f"assets in {time.time() - t0:.1f}s  duration={d:.1f}s  "
          f"wav={os.path.getsize(wav) / 2**20:.1f}MB f32={os.path.getsize(f32) / 2**20:.1f}MB")


if __name__ == "__main__":
    main()