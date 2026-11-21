"""取流：A 直链下载（主路径） / B yt-dlp 兜底。"""
import argparse, os, sys, time, urllib.request, subprocess

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def download(url, out):
    t0 = time.time()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://www.douyin.com/",
        "Accept": "*/*",
    })
    tmp = out + ".part"
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            buf = r.read(1 << 20)
            if not buf:
                break
            f.write(buf)
            got += len(buf)
    os.replace(tmp, out)
    print(f"downloaded {got / 2**20:.1f} MB in {time.time() - t0:.1f}s -> {out}")
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--play-url", help="aweme detail 接口返回的 play_addr 直链（主路径）")
    ap.add_argument("--url", help="分享/页面链接（yt-dlp 兜底）")
    ap.add_argument("--cookie-browser", default="", help="如 edge / chrome，仅兜底用，注意 cookie 暴露风险")
    ap.add_argument("--out", default=os.path.join("tmp-douyin", "video.mp4"))
    a = ap.parse_args()

    if a.play_url:
        download(a.play_url, a.out)
        return

    if not a.url:
        print("需要 --play-url 或 --url", file=sys.stderr)
        sys.exit(2)

    cmd = ["yt-dlp", "-o", a.out, "--no-playlist", "--force-overwrites"]
    if a.cookie_browser:
        cmd += ["--cookies-from-browser", a.cookie_browser]
        print("warn: 使用浏览器 cookie，属登录态外带，注意风险")
    cmd.append(a.url)
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()[-3:]
        print("yt-dlp 失败：\n" + "\n".join(tail), file=sys.stderr)
        print("提示：改用页内 API 取 play_addr（浏览器已登录），或加 --cookie-browser edge", file=sys.stderr)
        sys.exit(1)
    print(f"yt-dlp done in {time.time() - t0:.1f}s -> {a.out}")


if __name__ == "__main__":
    main()