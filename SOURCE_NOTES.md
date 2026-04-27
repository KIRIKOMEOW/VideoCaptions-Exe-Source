# VideoCaptions EXE Source

This folder is a standalone copy of the source files used to build `VideoCaptions.exe`.

Important files:
- `src/handler/gui.py`: Windows GUI entry point
- `src/service/youtube.py`: YouTube caption logic
- `src/service/bilibili.py`: Bilibili caption and ASR audio download logic
- `src/core/asr.py`: Whisper ASR logic
- `VideoCaptions.spec`: PyInstaller build spec
- `build_exe.ps1`: Windows build script

Build command:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Output:

```text
dist\VideoCaptions.exe
```
