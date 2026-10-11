# Windows 测试步骤（阶段 0）

目标：在 Windows 上转写 `sample.mp4`，把屏幕最后的 JSON 摘要贴回给 Claude。
只需要装一个工具：uv。不需要装 Python、git、ffmpeg。

## 1. 安装 uv（只做一次）
1. 按 Win 键，输入 `powershell`，打开“Windows PowerShell”。
2. 复制下面一行，粘贴进去，按回车：
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. 看到 `everything's installed!` 后，**关掉这个 PowerShell 窗口**（新窗口才能识别 uv）。

## 2. 下载仓库
1. 打开 https://github.com/Vincennes-Wang/lecture-transcriber/archive/refs/heads/main.zip ，下载 ZIP。
2. 右键 ZIP →“全部解压缩”→“提取”。
3. Windows 会多套一层文件夹：`lecture-transcriber-main\lecture-transcriber-main\`。**双击进到里面那一层**，能看到 `scripts`、`docs`、`pyproject.toml` 的那个文件夹才是正确位置。下面所说的 `lecture-transcriber-main` 都指这一层。

## 3. 放入测试视频
1. 在 `lecture-transcriber-main` 里新建文件夹 `private`。
2. 把 `sample.mp4` 放进 `private`。

## 4. 运行
1. 打开 `lecture-transcriber-main` 文件夹，点击窗口顶部的地址栏，输入 `powershell`，按回车。会打开一个已经位于这个文件夹的 PowerShell。
2. 复制下面一行，粘贴，按回车：
   ```powershell
   uv run scripts/bench.py private\sample.mp4
   ```
3. 第一次运行会自动下载 Python、依赖和模型（模型约 1.6 GB），需要几分钟。之后再运行不会重复下载。
4. 运行中会每分钟显示一次进度，例如 `00:03:12 / 00:08:57  已用 95 秒`。
5. 结束时屏幕显示 `===== 摘要（整段复制）=====`，下面是一段 `{ ... }`。

## 5. 贴回结果
- 复制从 `{` 到 `}` 的整段文字，贴给 Claude。
- 同一段内容也保存在 `private\out\` 下的 `.json` 文件里。
- 不要贴 `.txt` 文件（那是课程原文）。

## 常见情况
| 现象 | 处理 |
|---|---|
| `uv : 无法识别…` | 第 1 步后没有重开 PowerShell。关掉窗口重开。 |
| 出现 `symlinks` 相关的黄色警告 | 不影响结果，忽略。 |
| `找不到文件` | 检查视频是否在 `private` 文件夹里，文件名是否是 `sample.mp4`。 |
| 下载很慢或中断 | 重新运行同一条命令，会接着下载。 |
