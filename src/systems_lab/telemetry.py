"""Durable delivery of allowlisted gateway audit events as OpenTelemetry spans."""

from __future__ import annotations

import math
import os
import threading
from collections.abc import Callable
from typing import Any, Protocol

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    SpanKind,
    Status,
    StatusCode,
    TraceFlags,
)


class Journal(Protocol):
    def pending(self, limit: int = 100) -> list[dict[str, Any]]: ...

    def acknowledge(self, sequences: list[int], error: str | None) -> None: ...

    def verify(self) -> dict[str, Any]: ...

    def worker_started(self, run_id: str, actor: str) -> float | None: ...


class _EventIdGenerator(IdGenerator):
    """Supply the journal's stable IDs to the SDK's public span creation path."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self._index = 0

    def generate_trace_id(self) -> int:
        return int(self._events[self._index]["trace_id"], 16)

    def generate_span_id(self) -> int:
        value = int(self._events[self._index]["span_id"], 16)
        self._index += 1
        return value

    def is_trace_id_random(self) -> bool:
        return False


class TelemetryDelivery:
    """Send journal events at least once; the journal remains the durable source."""

    _BATCH_SIZE = 100
    _INTERVAL_SECONDS = 1.0
    _EXPORT_ERROR = "telemetry export failed"
    _INTEGRITY_ERROR = "journal integrity verification failed"

    def __init__(self, journal: Journal, exporter: SpanExporter | None = None) -> None:
        self.journal = journal
        self.exporter = exporter
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._flush_lock = threading.Lock()
        self._stop_lock = threading.Lock()
        self._stopped = False

    @property
    def enabled(self) -> bool:
        return self.exporter is not None

    @classmethod
    def from_environment(cls, journal: Journal) -> TelemetryDelivery:
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
        if not endpoint:
            return cls(journal)
        # Pass headers explicitly so ambient OTEL header variables cannot add secrets.
        try:
            exporter = OTLPSpanExporter(endpoint=endpoint, headers={}, timeout=2)
        except Exception:
            return cls(journal)
        return cls(journal, exporter)

    def flush_once(self) -> bool:
        if not self.enabled:
            return True

        with self._flush_lock:
            try:
                events = self.journal.pending(limit=self._BATCH_SIZE)
            except Exception:
                return False
            if not events:
                return True

            sequences = [int(event["sequence"]) for event in events]
            try:
                integrity = self.journal.verify()
                if not integrity.get("valid", False):
                    self.journal.acknowledge(sequences, self._INTEGRITY_ERROR)
                    return False
                spans = self._make_spans(events)
                result = self.exporter.export(spans)  # type: ignore[union-attr]
                if result is not SpanExportResult.SUCCESS:
                    self.journal.acknowledge(sequences, self._EXPORT_ERROR)
                    return False
                self.journal.acknowledge(sequences, None)
                return True
            except Exception:
                # Never persist exception text: exporters may include endpoints or headers.
                try:
                    self.journal.acknowledge(sequences, self._EXPORT_ERROR)
                except Exception:
                    pass
                return False

    def start(self) -> None:
        if not self.enabled or self._stopped:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="systems-lab-telemetry", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True
            self._stop_event.set()
            thread = self._thread
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=3)
            if self.exporter is not None:
                try:
                    self.exporter.shutdown()
                except Exception:
                    pass

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.flush_once()
            self._stop_event.wait(self._INTERVAL_SECONDS)

    def _make_spans(self, events: list[dict[str, Any]]) -> list[Any]:
        memory_exporter = InMemorySpanExporter()
        provider = TracerProvider(
            resource=Resource({"service.name": "agent-systems-lab.gateway"}),
            sampler=ALWAYS_ON,
            id_generator=_EventIdGenerator(events),
        )
        provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
        tracer = provider.get_tracer("systems_lab.gateway.audit")
        try:
            for event in events:
                attributes = _safe_attributes(event, self.journal.worker_started)
                parent_id = event.get("parent_span_id", "")
                context = Context()
                if parent_id:
                    parent = SpanContext(
                        trace_id=int(event["trace_id"], 16),
                        span_id=int(parent_id, 16),
                        is_remote=True,
                        trace_flags=TraceFlags(TraceFlags.SAMPLED),
                    )
                    context = trace.set_span_in_context(NonRecordingSpan(parent), Context())
                end_ns = int(float(event["timestamp"]) * 1_000_000_000)
                duration_ms = attributes.get("lab.duration_ms")
                duration_ns = int(duration_ms * 1_000_000) if duration_ms is not None else 0
                span = tracer.start_span(
                    str(event["action"]),
                    context=context,
                    kind=SpanKind.INTERNAL,
                    attributes=attributes,
                    start_time=end_ns - duration_ns,
                )
                if _is_error_event(event):
                    span.set_status(Status(StatusCode.ERROR))
                span.end(end_time=end_ns)
            return list(memory_exporter.get_finished_spans())
        finally:
            provider.shutdown()


def _safe_attributes(
    event: dict[str, Any], worker_started: Callable[[str, str], float | None]
) -> dict[str, str | int | float | bool]:
    """Copy only stable identifiers and fixed audit fields, never event details."""
    attributes: dict[str, str | int | float | bool] = {
        "lab.sequence": int(event["sequence"]),
        "lab.event_id": str(event["event_id"]),
        "lab.run_id": str(event["run_id"]),
        "lab.actor": str(event["actor"]),
        "lab.action": str(event["action"]),
        "lab.decision": str(event["decision"]),
        "lab.model_mode": str(event["model_mode"]),
        "lab.hash": str(event["hash"]),
    }
    data = event.get("data")
    duration_ms: Any = data.get("duration_ms") if isinstance(data, dict) else None
    if str(event["action"]) in {
        "worker.completed",
        "worker.failed",
        "worker.timed_out",
    }:
        started = worker_started(str(event["run_id"]), str(event["actor"]))
        if started is not None:
            duration_ms = max(0, int((float(event["timestamp"]) - started) * 1000))
    if (
        isinstance(duration_ms, (int, float))
        and not isinstance(duration_ms, bool)
        and math.isfinite(float(duration_ms))
        and duration_ms >= 0
    ):
        attributes["lab.duration_ms"] = float(duration_ms)
    return attributes


def _is_error_event(event: dict[str, Any]) -> bool:
    return str(event["decision"]).lower() in {"deny", "error"} or str(event["action"]).lower() in {
        "worker.failed",
        "worker.timed_out",
    }
