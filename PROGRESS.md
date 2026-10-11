# PROGRESS
- 状态：进行中
- 当前阶段：阶段 0 验证（Mac 部分完成，等 Windows 数据）
- 累计用时：1.5
- 线上地址：

## 最近一次工作（2026-10-11）
- 完成：
  - 仓库 video-text 改名为 lecture-transcriber（公开），创建 CLAUDE.md、.gitignore、pyproject.toml、uv.lock。
  - `scripts/bench.py`：转写测试，边转写边写 txt，输出 JSON 摘要。
  - `scripts/analyze.py`：VAD 开/关对比、重复和碎片化检查（`--no-text` 不输出原文）。
  - `docs/windows-bench.md`、`docs/phase0-report.md`。
  - 依赖坑：av 19 删除了 `open(metadata_errors=...)`，faster-whisper 1.2.1 会报错。已固定 `av>=15,<18`。
- 验证结果：
  - 带中文、空格、重音字符的文件名能正常转写。
  - Mac 实测：sample 4.45 倍实时；full（1:08:41）cond 开 4.85 倍，cond 关 6.16 倍。
  - VAD 关闭没有带来额外的可疑文字；full 没有重复循环，但 cond 开时约 13 分钟后段落碎片化，cond 关解决。

## 下次从这里继续
1. 用户在 Windows 上按 `docs/windows-bench.md` 运行 sample.mp4，贴回 JSON；把数字填进 `docs/phase0-report.md`，推算 Windows 上 2 小时视频的耗时。
2. 确认内存问题：2 小时视频峰值内存是否超过 8 GB 电脑可用内存。
3. 阶段 1 计划（正式工具）：默认 VAD 开、cond 关；过滤片尾固定短语幻觉；输出分块文本方便粘贴。

## 未解决问题
- Mac 本地文件夹仍叫 `~/code/video-text`（GitHub 已改名）。用户可选择改名：关闭 Claude Code 后 `mv ~/code/video-text ~/code/lecture-transcriber`，再删除 `.venv`（`uv run` 会自动重建）。
- 用户反馈找不到某个文件夹；已在 `docs/windows-bench.md` 补充 ZIP 解压后多一层文件夹的说明。如果指的是别的文件夹，下次确认。
- 峰值内存随视频长度增加（9 分钟 1.9 GB → 69 分钟 4.5 GB），原因未确认。
- Windows 上的速度未知。
