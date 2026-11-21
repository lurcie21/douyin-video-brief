"""按章取切片：只打印指定时间点附近的 N 行，避免把 459 行全文灌进上下文。"""
import argparse, os, re


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="tmp-douyin")
    ap.add_argument("--at", default="", help="逗号分隔的秒数，如 54,270,369,471,597,725")
    ap.add_argument("--lines", type=int, default=22, help="每章行数；骨架阶段 22，需要细节再单独取该章 40")
    a = ap.parse_args()
    path = os.path.join(a.dir, "transcript.txt")
    rows = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\[\s*([\d.]+)\]\s*(.*)", line.rstrip("\n"))
        if m:
            rows.append((float(m.group(1)), m.group(2)))
    if not a.at:
        print(f"{len(rows)} 行，{rows[0][0]:.1f}s..{rows[-1][0]:.1f}s；用 --at 指定章节秒数")
        return
    for at in [float(x) for x in a.at.split(",") if x.strip()]:
        idx = min(range(len(rows)), key=lambda i: abs(rows[i][0] - at))
        lo, hi = max(0, idx - a.lines // 3), min(len(rows), idx + a.lines)
        print(f"\n===== 约 {at:.0f}s（第 {lo + 1}-{hi} 行）=====")
        for t, txt in rows[lo:hi]:
            print(f"[{t:7.1f}] {txt}")


if __name__ == "__main__":
    main()