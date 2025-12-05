from __future__ import annotations

import queue
from threading import Event, Lock, Thread
from typing import Optional

import structlog

from chatterbug.app.metrics import metrics
from chatterbug.domain.model import (
    AudioChunk,
    AudioSource,
    EngineKind,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptionResult,
    TranscriptSink,
)
from chatterbug.domain.exceptions import SessionError
from chatterbug.polish.base import Polisher

logger = structlog.get_logger()

# Timeout for graceful thread shutdown
THREAD_JOIN_TIMEOUT_SEC = 10.0

class TranscriptionSession:
    """Wires an AudioSource into a TranscriptionEngine and pushes results to a sink."""

    def __init__(self) -> None:
        self._thread: Optional[Thread] = None
        self._threads: list[Thread] = []
        self._stop_event = Event()
        self._exception: Optional[BaseException] = None
        self._audio_queue: queue.Queue[AudioChunk | object] | None = None
        self._segment_queue: queue.Queue[TranscriptSegment | object] | None = None
        self._polisher: Optional[Polisher] = None
        self._start_stop_lock = Lock()  # Protect against concurrent start/stop
        # Sentinels to signal stage completion
        self._audio_stop = object()
        self._segment_stop = object()

    def start(
        self,
        source: AudioSource,
        engine: TranscriptionEngine,
        sink: TranscriptSink,
        options: TranscriptionOptions,
        engine_kind: EngineKind = "whisper_turbo",
        polisher: Optional[Polisher] = None,
    ) -> None:
        with self._start_stop_lock:
            if any(t.is_alive() for t in self._threads):
                raise SessionError("TranscriptionSession already running")
            self._stop_event.clear()
            self._exception = None
            self._polisher = polisher
            self._audio_queue = queue.Queue(maxsize=200) # Increased buffer
            self._segment_queue = queue.Queue(maxsize=32)
            self._threads = [
                Thread(
                    target=self._run_source,
                    args=(source,),
                    daemon=True,
                    name="CaptureThread"
                ),
                Thread(
                    target=self._run_engine,
                    args=(engine, options),
                    daemon=True,
                    name="EngineThread"
                ),
                Thread(
                    target=self._run_sink,
                    args=(sink, engine, engine_kind),
                    daemon=True,
                    name="SinkThread"
                ),
            ]
            for thread in self._threads:
                thread.start()

    def stop(self) -> None:
        with self._start_stop_lock:
            self._stop_event.set()
            # Unblock queues so workers can exit promptly
            if self._audio_queue is not None:
                try:
                    self._audio_queue.put_nowait(self._audio_stop)
                except Exception:
                    pass
            if self._segment_queue is not None:
                try:
                    self._segment_queue.put_nowait(self._segment_stop)
                except Exception:
                    pass
        # Join threads outside the lock to avoid deadlock
        # Use timeout to prevent hanging indefinitely
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=THREAD_JOIN_TIMEOUT_SEC)
                if thread.is_alive():
                    logger.warning(f"Thread {thread.name} did not terminate within timeout")

    def join(self, timeout: float | None = None) -> None:
        import time

        start = time.monotonic()
        for thread in self._threads:
            remaining = None
            if timeout is not None:
                elapsed = time.monotonic() - start
                remaining = max(0.0, timeout - elapsed)
            thread.join(timeout=remaining)
            if timeout is not None and (time.monotonic() - start) >= timeout:
                break
        if self._exception:
            raise self._exception

    def _run_source(self, source: AudioSource) -> None:
        """Stream audio into a bounded queue with backpressure."""
        assert self._audio_queue is not None
        try:
            for chunk in source.stream():
                if self._stop_event.is_set():
                    break
                # Backpressure: wait for consumers but allow cancellation.
                while not self._stop_event.is_set():
                    try:
                        self._audio_queue.put(chunk, timeout=0.1)
                        break
                    except queue.Full:
                        continue
        except BaseException as exc:
            self._exception = self._exception or exc
            self._stop_event.set()
        finally:
            try:
                self._audio_queue.put(self._audio_stop, timeout=0.1)
            except Exception:
                pass
            stop_fn = getattr(source, "stop", None)
            if callable(stop_fn):
                try:
                    stop_fn()
                except Exception:
                    pass

    def _run_engine(self, engine: TranscriptionEngine, options: TranscriptionOptions) -> None:
        """Consume audio queue, push to engine, poll segments."""
        assert self._audio_queue is not None
        assert self._segment_queue is not None

        try:
            engine.start(options)
            
            while not self._stop_event.is_set():
                try:
                    item = self._audio_queue.get(timeout=0.05)
                except queue.Empty:
                    # Poll segments even if no audio arrived
                    self._poll_and_emit(engine)
                    continue

                if item is self._audio_stop:
                    break
                
                if isinstance(item, AudioChunk):
                    # Convert AudioChunk to bytes and timestamp
                    ts_ms = int(item.start_s * 1000)
                    engine.push_audio(item.samples, ts_ms)
                    
                    # Update metrics
                    metrics.audio_queue_depth = self._audio_queue.qsize()
                    metrics.segment_queue_depth = self._segment_queue.qsize()
                
                self._poll_and_emit(engine)
            
            # Flush remaining audio
            engine.flush()
            self._poll_and_emit(engine)

        except BaseException as exc:
            logger.exception("Engine thread failed")
            self._exception = self._exception or exc
            self._stop_event.set()
        finally:
            try:
                self._segment_queue.put(self._segment_stop, timeout=0.1)
            except Exception:
                pass

    def _poll_and_emit(self, engine: TranscriptionEngine) -> None:
        segments = engine.poll_segments()
        for seg in segments:
            while not self._stop_event.is_set():
                try:
                    self._segment_queue.put(seg, timeout=0.1)
                    break
                except queue.Full:
                    continue

    def _run_sink(
        self, sink: TranscriptSink, engine: TranscriptionEngine, engine_kind: EngineKind
    ) -> None:
        """Drain segments, build final result, and surface errors."""
        assert self._segment_queue is not None
        segments: list[TranscriptSegment] = []
        try:
            while True:
                try:
                    item = self._segment_queue.get(timeout=0.1)
                except queue.Empty:
                    if self._stop_event.is_set() and self._exception:
                        break
                    continue
                if item is self._segment_stop:
                    break
                segment = item  # type: ignore[assignment]
                if self._stop_event.is_set():
                    continue
                segments.append(segment)
                sink.handle_segment(segment)

            stopped_by_user = self._stop_event.is_set() and self._exception is None
            # Only surface completion if not explicitly cancelled
            if not stopped_by_user:
                warnings = tuple()
                if self._exception is not None:
                    warnings = (f"error: {self._exception}",)
                # Normalize whitespace to avoid double spaces from engine outputs
                raw_text = " ".join(seg.text.strip() for seg in segments)
                normalized_text = " ".join(raw_text.split())
                polished_text = (
                    self._polisher.polish(normalized_text)
                    if self._polisher is not None
                    else normalized_text
                )
                result = TranscriptionResult(
                    text=polished_text,
                    segments=tuple(segments),
                    model_name=getattr(engine, "model_name", "unknown"),
                    device=getattr(engine, "device", "unknown"),
                    precision=getattr(engine, "precision", "unknown"),
                    engine=engine_kind,
                    duration_s=segments[-1].end_s if segments else 0.0,
                    warnings=warnings,
                )
                sink.complete(result)
        except BaseException as exc:
            self._exception = self._exception or exc
            self._stop_event.set()
