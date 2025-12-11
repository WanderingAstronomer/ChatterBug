"""CLI commands for the warm model daemon."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console

from vociferous.server import (
    DaemonClient,
    is_daemon_running,
    get_daemon_pid,
    run_daemon,
    DEFAULT_SOCKET_PATH,
    DEFAULT_PID_FILE,
)


console = Console()


def register_daemon(app: typer.Typer) -> None:
    """Register the daemon command and its subcommands."""
    
    daemon_app = typer.Typer(
        help="Manage the warm model daemon for fast transcription",
        no_args_is_help=True,
    )
    
    @daemon_app.command("start")
    def start_cmd(
        foreground: bool = typer.Option(
            False,
            "--foreground", "-f",
            help="Run in foreground (don't daemonize)",
        ),
        model: str = typer.Option(
            "nvidia/canary-qwen-2.5b",
            "--model", "-m",
            help="Model to load",
        ),
    ) -> None:
        """Start the warm model daemon.
        
        Keeps the Canary-Qwen model loaded in GPU memory,
        reducing transcription time from ~30s to ~2-5s.
        """
        if is_daemon_running():
            pid = get_daemon_pid()
            console.print(f"[yellow]Daemon already running (PID: {pid})[/yellow]")
            return
        
        if foreground:
            console.print("Starting daemon in foreground...")
            console.print("Press Ctrl+C to stop")
            run_daemon(
                socket_path=DEFAULT_SOCKET_PATH,
                pid_file=DEFAULT_PID_FILE,
                model_name=model,
            )
        else:
            console.print("Starting daemon in background...")
            
            # Spawn a new process that runs the daemon
            env = os.environ.copy()
            
            # Run the daemon module directly
            cmd = [
                sys.executable, "-m", "vociferous.server.daemon",
            ]
            
            # Start detached process
            with open("/dev/null", "r") as devnull_r:
                with open("/tmp/vociferous-daemon.log", "a") as log:
                    subprocess.Popen(
                        cmd,
                        stdin=devnull_r,
                        stdout=log,
                        stderr=log,
                        start_new_session=True,
                        env=env,
                    )
            
            # Wait for startup
            console.print("Waiting for model to load (this may take ~16s)...")
            
            # Poll for daemon to be ready
            for i in range(60):  # Wait up to 60 seconds
                time.sleep(1)
                if is_daemon_running():
                    try:
                        client = DaemonClient()
                        status = client.status()
                        if status.model_loaded:
                            console.print(
                                f"[green]✓ Daemon started (PID: {get_daemon_pid()})[/green]"
                            )
                            console.print(f"  Model: {status.model_name}")
                            console.print(f"  Device: {status.device}")
                            console.print(f"\nLogs: /tmp/vociferous-daemon.log")
                            return
                    except Exception:
                        pass
                if i % 5 == 0:
                    console.print(f"  Still loading... ({i}s)")
            
            console.print("[red]✗ Daemon failed to start[/red]")
            console.print("Check logs: /tmp/vociferous-daemon.log")
            raise typer.Exit(1)

    @daemon_app.command("stop")
    def stop_cmd() -> None:
        """Stop the warm model daemon."""
        if not is_daemon_running():
            console.print("Daemon is not running")
            return
        
        pid = get_daemon_pid()
        
        try:
            # Try graceful shutdown via socket first
            client = DaemonClient()
            client.shutdown()
            console.print("Shutdown signal sent, waiting...")
            
            # Wait for process to exit
            for _ in range(10):
                time.sleep(0.5)
                if not is_daemon_running():
                    console.print(f"[green]✓ Daemon stopped (was PID: {pid})[/green]")
                    return
            
            # Force kill if still running
            if pid:
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
                
        except Exception as e:
            # Try direct kill
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    console.print(f"[green]✓ Daemon killed (PID: {pid})[/green]")
                except ProcessLookupError:
                    console.print("Daemon process not found")
                except Exception as kill_error:
                    console.print(f"[red]Failed to stop daemon: {kill_error}[/red]")
                    raise typer.Exit(1)
            else:
                console.print(f"[red]Failed to stop daemon: {e}[/red]")
                raise typer.Exit(1)
        
        # Clean up stale files
        try:
            DEFAULT_SOCKET_PATH.unlink(missing_ok=True)
            DEFAULT_PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        
        console.print("[green]✓ Daemon stopped[/green]")

    @daemon_app.command("status")
    def status_cmd() -> None:
        """Check daemon status."""
        if not is_daemon_running():
            console.print("[yellow]Daemon: not running[/yellow]")
            return
        
        pid = get_daemon_pid()
        
        try:
            client = DaemonClient()
            status = client.status()
            
            console.print("[green]Daemon: running[/green]")
            console.print(f"  PID: {pid}")
            console.print(f"  Model: {status.model_name}")
            console.print(f"  Device: {status.device}")
            console.print(f"  Model loaded: {status.model_loaded}")
            console.print(f"  Uptime: {status.uptime_seconds:.1f}s")
            console.print(f"  Requests served: {status.requests_served}")
            console.print(f"  Socket: {DEFAULT_SOCKET_PATH}")
            
        except Exception as e:
            console.print(f"[yellow]Daemon: running (PID: {pid}) but unresponsive[/yellow]")
            console.print(f"  Error: {e}")

    @daemon_app.command("logs")
    def logs_cmd(
        lines: int = typer.Option(
            50,
            "--lines", "-n",
            help="Number of lines to show",
        ),
    ) -> None:
        """Show daemon logs."""
        log_path = Path("/tmp/vociferous-daemon.log")
        if not log_path.exists():
            console.print("No logs found")
            return
        
        # Tail last N lines
        all_lines = log_path.read_text().splitlines()
        for line in all_lines[-lines:]:
            console.print(line)
    
    app.add_typer(daemon_app, name="daemon")

