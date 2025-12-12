"""CLI commands for managing the warm model daemon (FastAPI/uvicorn).

The daemon keeps the Canary-Qwen model loaded in GPU memory for fast
transcription. It uses FastAPI + uvicorn for HTTP-based communication.

Commands:
    vociferous daemon start   - Start the daemon
    vociferous daemon stop    - Stop the daemon
    vociferous daemon status  - Check daemon status
    vociferous daemon logs    - View daemon logs
    vociferous daemon restart - Restart the daemon
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console

import requests

console = Console()

# Daemon configuration
DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 8765
DAEMON_MODULE = "vociferous.server.api:app"

# File paths
CACHE_DIR = Path.home() / ".cache" / "vociferous"
PID_FILE = CACHE_DIR / "daemon.pid"
LOG_FILE = CACHE_DIR / "daemon.log"


def _ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _is_daemon_running() -> bool:
    """Check if daemon is running by pinging health endpoint."""
    try:
        response = requests.get(
            f"http://{DAEMON_HOST}:{DAEMON_PORT}/health",
            timeout=2.0,
        )
        return response.ok
    except Exception:
        return False


def _get_daemon_pid() -> int | None:
    """Read daemon PID from PID file."""
    if not PID_FILE.exists():
        return None

    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is actually running
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file is stale or invalid
        PID_FILE.unlink(missing_ok=True)
        return None


def _write_pid_file(pid: int) -> None:
    """Write daemon PID to PID file."""
    _ensure_cache_dir()
    PID_FILE.write_text(str(pid))


def _remove_pid_file() -> None:
    """Remove PID file."""
    PID_FILE.unlink(missing_ok=True)


def register_daemon(app: typer.Typer) -> None:
    """Register the daemon command and its subcommands."""

    daemon_app = typer.Typer(
        help="Manage the warm model daemon for fast transcription",
        no_args_is_help=True,
    )

    @daemon_app.command("start")
    def start_cmd(
        detach: bool = typer.Option(
            True,
            "--detach/--foreground",
            "-d/-f",
            help="Run daemon in background (default) or foreground",
        ),
        port: int = typer.Option(
            DAEMON_PORT,
            "--port", "-p",
            help="Port to listen on",
        ),
    ) -> None:
        """Start the warm model daemon.

        Keeps the Canary-Qwen model loaded in GPU memory,
        reducing transcription time from ~30s to ~2-5s.
        """
        # Check if already running
        if _is_daemon_running():
            console.print("[yellow]✓ Daemon is already running[/yellow]")
            pid = _get_daemon_pid()
            if pid:
                console.print(f"  PID: {pid}")
            return

        # Clean up stale PID file
        _remove_pid_file()
        _ensure_cache_dir()

        console.print("Starting warm model daemon...")
        console.print(f"  Host: {DAEMON_HOST}:{port}")
        console.print(f"  Logs: {LOG_FILE}")
        console.print("")
        console.print("⏳ Loading model (this takes ~16 seconds)...")

        # Prepare uvicorn command
        cmd = [
            sys.executable, "-m", "uvicorn",
            DAEMON_MODULE,
            "--host", DAEMON_HOST,
            "--port", str(port),
            "--log-level", "info",
        ]

        if detach:
            # Run in background
            with open(LOG_FILE, "w") as log_file:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from terminal
                )

            _write_pid_file(process.pid)

            # Wait for server to be ready
            for i in range(60):  # Wait up to 60 seconds
                time.sleep(1)
                if _is_daemon_running():
                    console.print(
                        f"[green]✓ Daemon started successfully (PID: {process.pid})[/green]"
                    )
                    console.print("")
                    console.print("  View logs:  vociferous daemon logs")
                    console.print("  Check status: vociferous daemon status")
                    return
                if i > 0 and i % 10 == 0:
                    console.print(f"  Still loading... ({i}s)")

            console.print(
                "[red]✗ Daemon failed to start within 60 seconds[/red]",
            )
            console.print(f"  Check logs: {LOG_FILE}")
            raise typer.Exit(1)

        else:
            # Run in foreground
            console.print("Running in foreground (Ctrl+C to stop)...")
            try:
                subprocess.run(cmd)
            except KeyboardInterrupt:
                console.print("\nStopping daemon...")

    @daemon_app.command("stop")
    def stop_cmd() -> None:
        """Stop the warm model daemon."""
        pid = _get_daemon_pid()

        if not pid:
            if _is_daemon_running():
                console.print(
                    "[yellow]⚠️  Daemon is running but PID file not found[/yellow]",
                )
                console.print(
                    "   Try: pkill -f 'uvicorn.*vociferous.server.api'",
                )
            else:
                console.print("[green]✓ Daemon is not running[/green]")
            return

        console.print(f"Stopping daemon (PID: {pid})...")

        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)

            # Wait for process to exit
            for _ in range(10):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    # Process has exited
                    _remove_pid_file()
                    console.print("[green]✓ Daemon stopped[/green]")
                    return

            # Still running after 5 seconds - force kill
            console.print(
                "[yellow]⚠️  Daemon did not stop gracefully, forcing...[/yellow]",
            )
            os.kill(pid, signal.SIGKILL)
            _remove_pid_file()
            console.print("[green]✓ Daemon force-stopped[/green]")

        except ProcessLookupError:
            # Process already gone
            _remove_pid_file()
            console.print("[green]✓ Daemon already stopped[/green]")

        except PermissionError:
            console.print(f"[red]✗ Permission denied to stop PID {pid}[/red]")
            raise typer.Exit(1)

    @daemon_app.command("status")
    def status_cmd() -> None:
        """Check daemon status."""
        is_running = _is_daemon_running()
        pid = _get_daemon_pid()

        if is_running:
            console.print("[green]✓ Daemon is running[/green]")
            if pid:
                console.print(f"  PID: {pid}")

            # Get health info
            try:
                response = requests.get(
                    f"http://{DAEMON_HOST}:{DAEMON_PORT}/health",
                    timeout=2.0,
                )
                if response.ok:
                    data = response.json()
                    console.print(f"  Model: {data.get('model_name', 'unknown')}")

                    uptime = data.get("uptime_seconds")
                    if uptime:
                        if uptime >= 3600:
                            uptime_str = f"{uptime / 3600:.1f} hours"
                        elif uptime >= 60:
                            uptime_str = f"{uptime / 60:.1f} minutes"
                        else:
                            uptime_str = f"{uptime:.1f} seconds"
                        console.print(f"  Uptime: {uptime_str}")

                    requests_handled = data.get("requests_handled", 0)
                    console.print(f"  Requests handled: {requests_handled}")
            except Exception:
                pass

        else:
            console.print("[yellow]✗ Daemon is not running[/yellow]")
            if pid:
                console.print(f"  ⚠️  Stale PID file found: {pid}")

    @daemon_app.command("logs")
    def logs_cmd(
        lines: int = typer.Option(
            50,
            "--lines", "-n",
            help="Number of lines to show",
        ),
        follow: bool = typer.Option(
            False,
            "--follow", "-f",
            help="Follow log output",
        ),
    ) -> None:
        """Show daemon logs."""
        if not LOG_FILE.exists():
            console.print("[yellow]No log file found[/yellow]")
            console.print(f"Expected location: {LOG_FILE}")
            raise typer.Exit(1)

        if follow:
            # Follow logs like 'tail -f'
            try:
                subprocess.run(["tail", "-f", str(LOG_FILE)])
            except KeyboardInterrupt:
                pass
            except FileNotFoundError:
                # 'tail' not available (Windows?)
                console.print("[red]'tail' command not found[/red]")
                console.print("Use --lines instead of --follow")
                raise typer.Exit(1)
        else:
            # Show last N lines
            try:
                result = subprocess.run(
                    ["tail", "-n", str(lines), str(LOG_FILE)],
                    capture_output=True,
                    text=True,
                )
                console.print(result.stdout)
            except FileNotFoundError:
                # 'tail' not available, read file manually
                lines_list = LOG_FILE.read_text().splitlines()
                for line in lines_list[-lines:]:
                    console.print(line)

    @daemon_app.command("restart")
    def restart_cmd() -> None:
        """Restart the daemon."""
        console.print("Restarting daemon...")
        stop_cmd()
        time.sleep(1)
        start_cmd(detach=True, port=DAEMON_PORT)

    app.add_typer(daemon_app, name="daemon")

