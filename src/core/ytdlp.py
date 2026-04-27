"""Helpers for invoking yt-dlp without relying on console-script launchers."""

import contextlib
import io
import subprocess
import sys


def get_yt_dlp_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def run_yt_dlp(
    args: list[str],
    *,
    capture_output: bool = False,
    text: bool = False,
    check: bool = False,
) -> subprocess.CompletedProcess:
    if not getattr(sys, "frozen", False):
        return subprocess.run(
            get_yt_dlp_command() + args,
            capture_output=capture_output,
            text=text,
            check=check,
        )

    from yt_dlp import main as yt_dlp_main

    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            result = yt_dlp_main(args)
            returncode = int(result or 0)
        except SystemExit as exc:
            returncode = int(exc.code or 0) if isinstance(exc.code, int) else 1

    stdout_value = stdout.getvalue() if capture_output else None
    stderr_value = stderr.getvalue() if capture_output else None
    if capture_output and not text:
        stdout_value = stdout_value.encode()
        stderr_value = stderr_value.encode()

    completed = subprocess.CompletedProcess(
        ["yt-dlp", *args],
        returncode,
        stdout=stdout_value,
        stderr=stderr_value,
    )
    if check and returncode:
        raise subprocess.CalledProcessError(
            returncode,
            completed.args,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed
