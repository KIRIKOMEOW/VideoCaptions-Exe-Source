"""Small Windows GUI for downloading video captions to a text file."""

import asyncio
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.formatter import ResponseFormat
from core.text import make_safe_filename
from service import get_service


APP_TITLE = "Video Captions"
BROWSERS = ("auto", "chrome", "edge", "firefox", "brave")
MODELS = ("base", "small", "medium", "large")
LANGUAGE_OPTIONS = {
    "Chinese": "zh",
    "English": "en",
}


def _configure_bundled_tools_path() -> None:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        os.environ["PATH"] = f"{bundle_dir}{os.pathsep}{os.environ.get('PATH', '')}"


class CaptionDownloaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("760x540")
        self.minsize(680, 480)

        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.url = tk.StringVar()
        self.browser = tk.StringVar(value="auto")
        self.model = tk.StringVar(value="base")
        self.language = tk.StringVar(value="Chinese")
        self.status = tk.StringVar(value="Ready")
        self.last_file: Path | None = None
        self.events: queue.Queue[tuple[str, str | Path | None]] = queue.Queue()

        self._build_ui()
        self.after(100, self._process_events)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, padding=18)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(1, weight=1)
        root.rowconfigure(7, weight=1)

        title = ttk.Label(root, text="Video Captions", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 18))

        ttk.Label(root, text="URL").grid(row=1, column=0, sticky="w", pady=6)
        url_entry = ttk.Entry(root, textvariable=self.url)
        url_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=6)
        url_entry.focus_set()

        ttk.Label(root, text="Output folder").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(root, textvariable=self.output_dir).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Button(root, text="Browse", command=self._choose_output_dir).grid(
            row=2, column=2, sticky="ew", padx=(8, 0), pady=6
        )

        ttk.Label(root, text="Browser Cookie").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Combobox(root, textvariable=self.browser, values=BROWSERS, state="readonly", width=14).grid(
            row=3, column=1, sticky="w", pady=6
        )

        ttk.Label(root, text="Caption/ASR language").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Combobox(
            root,
            textvariable=self.language,
            values=tuple(LANGUAGE_OPTIONS),
            state="readonly",
            width=14,
        ).grid(row=4, column=1, sticky="w", pady=6)

        ttk.Label(root, text="ASR model").grid(row=5, column=0, sticky="w", pady=6)
        ttk.Combobox(root, textvariable=self.model, values=MODELS, state="readonly", width=14).grid(
            row=5, column=1, sticky="w", pady=6
        )

        actions = ttk.Frame(root)
        actions.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(14, 10))
        actions.columnconfigure(0, weight=1)

        self.download_button = ttk.Button(actions, text="Get captions and create TXT", command=self._start_download)
        self.download_button.grid(row=0, column=0, sticky="w")

        self.open_button = ttk.Button(actions, text="Open TXT", command=self._open_last_file, state="disabled")
        self.open_button.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.log = tk.Text(root, height=10, wrap="word", state="disabled")
        self.log.grid(row=7, column=0, columnspan=3, sticky="nsew")

        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=7, column=3, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        ttk.Label(root, textvariable=self.status).grid(row=8, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def _choose_output_dir(self) -> None:
        directory = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.home()))
        if directory:
            self.output_dir.set(directory)

    def _start_download(self) -> None:
        source = self.url.get().strip()
        output_dir = Path(self.output_dir.get().strip() or Path.home() / "Desktop")

        if not source:
            messagebox.showwarning(APP_TITLE, "Please enter a URL.")
            return
        if not output_dir.exists():
            messagebox.showwarning(APP_TITLE, "Output folder does not exist.")
            return

        self.download_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.last_file = None
        self._set_status("Working")
        self._append_log("Starting...")

        worker = threading.Thread(
            target=self._download_worker,
            args=(
                source,
                output_dir,
                self.browser.get(),
                self.model.get(),
                LANGUAGE_OPTIONS[self.language.get()],
            ),
            daemon=True,
        )
        worker.start()

    def _download_worker(
        self,
        source: str,
        output_dir: Path,
        browser: str,
        model: str,
        language: str,
    ) -> None:
        try:
            service = get_service(source, browser)
            if not service:
                raise ValueError("Unsupported URL or file source.")

            self.events.put(("log", f"Detected platform: {service.name}"))
            self.events.put(("log", f"Selected language: {language}"))
            result = asyncio.run(
                service.download_subtitle(
                    source,
                    ResponseFormat.TEXT,
                    model_size=model,
                    show_progress=False,
                    language=language,
                )
            )

            if "error" in result:
                details = result.get("message") or result.get("suggestion") or ""
                raise RuntimeError(f"{result['error']}\n{details}".strip())

            content = result.get("content", "")
            if not content.strip():
                raise RuntimeError("No caption content was returned.")

            video_title = result.get("video_title") or "captions"
            subtitle_count = result.get("subtitle_count", 0)
            filename = make_safe_filename(video_title).strip() or "captions"
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_path = output_dir / f"{filename}-{timestamp}.txt"
            output_path.write_text(content, encoding="utf-8")

            self.events.put(("success", output_path))
            self.events.put(("log", f"Saved: {output_path}"))
            self.events.put(("log", f"Caption count: {subtitle_count}"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _process_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if event == "log" and isinstance(payload, str):
                self._append_log(payload)
            elif event == "success" and isinstance(payload, Path):
                self.last_file = payload
                self.open_button.configure(state="normal")
                self.download_button.configure(state="normal")
                self._set_status("Done")
                messagebox.showinfo(APP_TITLE, f"Caption TXT created:\n{payload}")
            elif event == "error" and isinstance(payload, str):
                self.download_button.configure(state="normal")
                self._set_status("Error")
                self._append_log(payload)
                messagebox.showerror(APP_TITLE, payload)

        self.after(100, self._process_events)

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_status(self, value: str) -> None:
        self.status.set(value)

    def _open_last_file(self) -> None:
        if self.last_file and self.last_file.exists():
            os.startfile(self.last_file)  # type: ignore[attr-defined]
        elif self.last_file:
            webbrowser.open(str(self.last_file))


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--yt-dlp":
        from yt_dlp import main as yt_dlp_main

        sys.argv = ["yt-dlp", *sys.argv[2:]]
        raise SystemExit(yt_dlp_main())

    _configure_bundled_tools_path()
    app = CaptionDownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
