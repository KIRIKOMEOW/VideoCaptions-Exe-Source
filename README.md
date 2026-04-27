# Video Captions（EXE版本）

这是我自己为了方便用做的一个小工具。

有时候不想把视频从头看到尾，就想着直接把字幕搞下来，看一遍文字再去总结。所以就做了这个工具，支持B站和YouTube链接。

如果视频本身有字幕，就直接下载；  
如果没有，就用语音识别（ASR）把音频转成字幕。

另外我把它打包成了 `.exe`，这样可以直接用。

---

## 基于项目

这个工具是基于下面这个开源项目改的：

https://github.com/LuShan123888/Video-Captions

我主要是自己改了一下用起来不太顺的地方，修了一些bug，然后打包成了可执行文件。

---
## 关于 ASR 模型

这个工具里可以选不同的语音识别模型：

- base：速度比较快，精度一般（默认用这个）
- small：更快一点，但识别可能不太准
- medium：速度和精度比较平衡
- large：精度最高，但会比较慢

一般随便用用选 base 就够了，  
如果视频很重要、想要更准一点可以选 large。

## 能做什么

- 支持B站和YouTube视频链接
- 有字幕就直接下载
- 没字幕就自动生成
- 支持中文 / 英文
- 可以自己选输出路径
- 有一个简单的界面，直接点就能用

---

## 怎么用

1. 打开 `.exe`
2. 粘贴视频链接
3. 点按钮
4. 等一下生成 `.txt` 文件

---

## 说明

这个就是我自己平时用的小工具，没有做成特别完整的项目。




# Video Captions (EXE Version)

A simple tool I made mainly for myself.

Sometimes I don’t want to watch a full video, so I built this to quickly get the subtitles and read through them instead. It supports Bilibili and YouTube links.

If the video already has subtitles, it downloads them directly.  
If not, it uses an ASR model to generate subtitles from audio.

I also packaged it into a `.exe` so it can be used directly without setting up Python or any environment.

---

## Based on

This project is based on:

https://github.com/LuShan123888/Video-Captions

I mainly modified it for my own use, fixed some bugs, and packaged it into an executable.

---

## What it can do
Supports multiple ASR models with different speed-accuracy trade-offs (base, small, medium, large).

- Works with Bilibili and YouTube links
- Downloads existing subtitles if available
- Generates subtitles using ASR if not
- Supports Chinese / English
- Lets you choose output folder
- Simple GUI, no setup needed

---

## How to use

1. Open the `.exe`
2. Paste a video link
3. Click the button
4. Wait and get a `.txt` file

---

## Notes

This is just a personal-use tool, not a full polished project.  
