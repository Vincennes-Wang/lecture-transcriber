"""阶段 0 测试脚本：用 faster-whisper 转写一个视频，记录速度和资源占用。

用法：
    uv run scripts/bench.py private/sample.mp4 --vad on --cond on

输出（默认放在 private/out/）：
    <视频名>.<参数>.txt   每段一行，边转写边写入
    <视频名>.<参数>.json  摘要（同时打印到屏幕）
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

import av
import psutil
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent


def fmt_ts(seconds: float) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:05.2f}"


def on_off(value: str) -> bool:
    value = value.lower()
    if value not in ("on", "off"):
        raise argparse.ArgumentTypeError("只能是 on 或 off")
    return value == "on"


def video_duration(path: Path) -> float:
    with av.open(str(path)) as container:
        if container.duration is not None:
            return container.duration / av.time_base
        stream = container.streams.audio[0]
        return float(stream.duration * stream.time_base)


def cpu_model() -> str:
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, check=True,
            )
            return out.stdout.strip()
        if system == "Windows":
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        if system == "Linux":
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "unknown"


def os_version() -> str:
    system = platform.system()
    if system == "Darwin":
        return f"macOS {platform.mac_ver()[0]} ({platform.machine()})"
    if system == "Windows":
        release, version, _, _ = platform.win32_ver()
        return f"Windows {release} build {version} ({platform.machine()})"
    return platform.platform()


class PeakMemory:
    """后台线程每 0.2 秒读取一次进程内存（RSS），记录最大值。"""

    def __init__(self) -> None:
        self.proc = psutil.Process()
        self.peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self.proc.memory_info().rss)
            self._stop.wait(0.2)

    def __enter__(self) -> "PeakMemory":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()
        self.peak = max(self.peak, self.proc.memory_info().rss)

    def os_peak(self) -> int | None:
        """操作系统记录的峰值（比采样更准），拿不到时返回 None。"""
        info = self.proc.memory_info()
        if hasattr(info, "peak_wset"):  # Windows
            return info.peak_wset
        try:
            import resource

            maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return maxrss if platform.system() == "Darwin" else maxrss * 1024
        except ImportError:
            return None


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="faster-whisper 转写测试")
    parser.add_argument("video", type=Path, help="视频或音频文件路径")
    parser.add_argument("--vad", type=on_off, default=True, help="on/off，默认 on")
    parser.add_argument("--cond", type=on_off, default=True,
                        help="condition_on_previous_text，on/off，默认 on")
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--threads", type=int, default=psutil.cpu_count(logical=False) or 4,
                        help="CPU 线程数，默认等于物理核心数")
    parser.add_argument("--out", type=Path, default=ROOT / "private" / "out",
                        help="输出目录，默认 private/out")
    args = parser.parse_args()

    video = args.video.expanduser().resolve()
    if not video.is_file():
        print(f"找不到文件：{video}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"{args.model}.vad-{'on' if args.vad else 'off'}.cond-{'on' if args.cond else 'off'}.t{args.threads}"
    txt_path = args.out / f"{video.stem}.{tag}.txt"
    json_path = args.out / f"{video.stem}.{tag}.json"

    duration = video_duration(video)
    print(f"视频时长 {fmt_ts(duration)}，加载模型 {args.model} ...", file=sys.stderr)

    with PeakMemory() as mem:
        t0 = time.perf_counter()
        model = WhisperModel(args.model, device="cpu", compute_type="int8",
                             cpu_threads=args.threads)
        t_load = time.perf_counter() - t0

        t1 = time.perf_counter()
        segments, info = model.transcribe(
            str(video),
            language="fr",
            vad_filter=args.vad,
            condition_on_previous_text=args.cond,
        )
        n_segments = 0
        next_report = 0.0
        with txt_path.open("w", encoding="utf-8", newline="\n") as f:
            for seg in segments:
                f.write(f"[{fmt_ts(seg.start)} --> {fmt_ts(seg.end)}] {seg.text.strip()}\n")
                f.flush()
                n_segments += 1
                if seg.end >= next_report:
                    elapsed = time.perf_counter() - t1
                    print(f"  {fmt_ts(seg.end)} / {fmt_ts(duration)}  已用 {elapsed:.0f} 秒",
                          file=sys.stderr)
                    next_report = seg.end + 60
        t_transcribe = time.perf_counter() - t1

    summary = {
        "file": video.name,
        "model": args.model,
        "compute_type": "int8",
        "vad": args.vad,
        "condition_on_previous_text": args.cond,
        "threads": args.threads,
        "video_duration_s": round(duration, 1),
        "speech_duration_after_vad_s": round(info.duration_after_vad, 1),
        "model_load_s": round(t_load, 1),
        "transcribe_s": round(t_transcribe, 1),
        "realtime_factor": round(duration / t_transcribe, 2),
        "segments": n_segments,
        "peak_rss_mb_sampled": round(mem.peak / 2**20),
        "peak_rss_mb_os": round(p / 2**20) if (p := mem.os_peak()) else None,
        "cpu_model": cpu_model(),
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "ram_total_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "os": os_version(),
        "python": platform.python_version(),
        "transcript": txt_path.name,
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n===== 摘要（整段复制）=====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
