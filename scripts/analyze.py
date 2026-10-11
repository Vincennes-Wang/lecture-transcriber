"""阶段 0 分析脚本：读取 bench.py 生成的 txt，找可疑文字和重复片段。

用法：
    uv run scripts/analyze.py diff <开VAD.txt> <关VAD.txt>
        列出只在关闭 VAD 时出现的文字（在开 VAD 结果的相近时间里找不到）
    uv run scripts/analyze.py repeats <转写.txt>
        列出连续重复的段落、段内重复的短语

加 --no-text 只输出时间和统计，不输出原文（用于公开报告）。
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import zlib
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

LINE_RE = re.compile(r"^\[(\d+):(\d+):([\d.]+) --> (\d+):(\d+):([\d.]+)\] ?(.*)$")


@dataclass
class Seg:
    start: float
    end: float
    text: str

    @property
    def words(self) -> list[str]:
        return normalize(self.text).split()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def fmt_ts(seconds: float) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def load(path: Path) -> list[Seg]:
    segs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LINE_RE.match(line)
        if m:
            g = m.groups()
            start = int(g[0]) * 3600 + int(g[1]) * 60 + float(g[2])
            end = int(g[3]) * 3600 + int(g[4]) * 60 + float(g[5])
            segs.append(Seg(start, end, g[6]))
    return segs


def show(seg: Seg, no_text: bool, extra: str = "") -> str:
    head = f"  [{fmt_ts(seg.start)} - {fmt_ts(seg.end)}]{extra}"
    return head if no_text else f"{head}  {seg.text}"


def cmd_diff(a_path: Path, b_path: Path, no_text: bool, window: float, threshold: float) -> None:
    """B 中的段落，如果在 A 的相近时间窗口里找不到大部分词，就算可疑。"""
    a, b = load(a_path), load(b_path)
    suspicious = []
    for seg in b:
        words = seg.words
        if not words:
            continue
        nearby = set()
        for other in a:
            if other.end >= seg.start - window and other.start <= seg.end + window:
                nearby.update(other.words)
        coverage = sum(w in nearby for w in words) / len(words)
        if coverage < threshold:
            suspicious.append((seg, coverage))

    print(f"A（基准）：{a_path.name}，{len(a)} 段")
    print(f"B（对比）：{b_path.name}，{len(b)} 段")
    print(f"B 中可疑段落（±{window:.0f} 秒内 A 的词覆盖率 < {threshold:.0%}）：{len(suspicious)}")
    for seg, cov in suspicious:
        print(show(seg, no_text, f" 覆盖率 {cov:.0%} 词数 {len(seg.words)}"))


def compression_ratio(text: str) -> float:
    data = text.encode("utf-8")
    return len(data) / len(zlib.compress(data)) if data else 0.0


def cmd_repeats(path: Path, no_text: bool, similarity: float) -> None:
    segs = load(path)
    if not segs:
        print("没有读到段落")
        return
    total = segs[-1].end

    # 1. 连续重复的段落：相邻段落规范化后相同或高度相似
    runs: list[list[Seg]] = []
    current = [segs[0]]
    for prev, seg in zip(segs, segs[1:]):
        a, b = normalize(prev.text), normalize(seg.text)
        if a and b and SequenceMatcher(None, a, b).ratio() >= similarity:
            current.append(seg)
        else:
            if len(current) >= 2:
                runs.append(current)
            current = [seg]
    if len(current) >= 2:
        runs.append(current)

    # 2. 段内重复：压缩率高（Whisper 自己用 2.4 作为阈值）
    looped = [s for s in segs if compression_ratio(s.text) > 2.4]

    half = total / 2
    print(f"文件：{path.name}，{len(segs)} 段，最后时间 {fmt_ts(total)}")
    print(f"连续重复段落（相似度 ≥ {similarity:.0%}，≥ 2 段）：{len(runs)} 处，"
          f"其中后半段 {sum(r[0].start >= half for r in runs)} 处")
    for r in runs:
        print(f"  [{fmt_ts(r[0].start)} - {fmt_ts(r[-1].end)}] 连续 {len(r)} 段"
              + ("" if no_text else f"  {r[0].text}"))
    print(f"段内重复（压缩率 > 2.4）：{len(looped)} 段，"
          f"其中后半段 {sum(s.start >= half for s in looped)} 段")
    for s in looped:
        print(show(s, no_text, f" 压缩率 {compression_ratio(s.text):.1f}"))

    # 3. 文字密度：每 10 分钟的段数、词数、平均段长、以句号/问号/叹号结尾的比例
    #    循环时词数异常；段落碎片化时平均段长变短、标点比例下降
    print("每 10 分钟：段数 / 词数 / 平均段长(秒) / 句末标点比例")
    for i in range(int(total // 600) + 1):
        block = [s for s in segs if i * 600 <= s.start < (i + 1) * 600]
        if not block:
            continue
        mean_dur = sum(s.end - s.start for s in block) / len(block)
        punct = sum(s.text.rstrip()[-1:] in ".?!" for s in block) / len(block)
        print(f"  {fmt_ts(i * 600)}  {len(block):4d} / {sum(len(s.words) for s in block):5d}"
              f" / {mean_dur:4.1f} / {punct:4.0%}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff")
    d.add_argument("base", type=Path)
    d.add_argument("other", type=Path)
    d.add_argument("--window", type=float, default=10.0)
    d.add_argument("--threshold", type=float, default=0.5)
    r = sub.add_parser("repeats")
    r.add_argument("file", type=Path)
    r.add_argument("--similarity", type=float, default=0.9)
    for p in (d, r):
        p.add_argument("--no-text", action="store_true")
    args = parser.parse_args()

    if args.cmd == "diff":
        cmd_diff(args.base, args.other, args.no_text, args.window, args.threshold)
    else:
        cmd_repeats(args.file, args.no_text, args.similarity)
    return 0


if __name__ == "__main__":
    sys.exit(main())
