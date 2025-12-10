from __future__ import annotations

from pathlib import Path
from threading import Event, Thread
import wave

import typer

from vociferous.audio.components import RecorderComponent
from vociferous.domain.exceptions import DependencyError


def register_record(app: typer.Typer) -> None:
    @app.command("record", rich_help_panel="Audio Components")
    def record_cmd(
        output: Path | None = typer.Option(
            None,
            "--output",
            "-o",
            metavar="PATH",
            help="Optional output path (default: recording_<timestamp>.wav in CWD)",
        ),
        sample_rate: int = typer.Option(16000, help="Sample rate for capture (Hz)"),
        device: str | None = typer.Option(None, help="Optional sounddevice input name"),
    ) -> None:
        component = RecorderComponent(sample_rate=sample_rate, device_name=device)
        out_path = output or component.default_output_path()

        typer.echo("Ready to record. Press ENTER to START recording...")
        try:
            input()
        except KeyboardInterrupt:
            typer.echo("Cancelled.")
            raise typer.Exit(code=130)

        typer.echo("🔴 RECORDING... (press ENTER to STOP)")
        stop_event = Event()
        worker_error: list[Exception] = []

        def worker() -> None:
            try:
                component.record_to_file(out_path, stop_event)
            except DependencyError as exc:
                worker_error.append(exc)

        thread = Thread(target=worker, daemon=True)
        thread.start()

        try:
            input()
        except KeyboardInterrupt:
            pass
        stop_event.set()
        thread.join()

        if worker_error:
            typer.echo("Recording failed: sounddevice is required for microphone capture.", err=True)
            raise typer.Exit(code=2) from worker_error[0]

        size_mb = out_path.stat().st_size / (1024 * 1024)
        try:
            with wave.open(str(out_path), "rb") as wf:
                duration_s = wf.getnframes() / float(wf.getframerate())
        except Exception:
            duration_s = 0.0

        typer.echo(f"✓ Stopped. Saved: {out_path.name} ({size_mb:.2f} MB, {duration_s:.1f}s)")

    return None
