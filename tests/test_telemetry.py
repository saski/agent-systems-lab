from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from sqlalchemy import create_engine

from systems_lab.journal import Journal
from systems_lab.telemetry import TelemetryDelivery


class _Receiver(BaseHTTPRequestHandler):
    requests: list[ExportTraceServiceRequest] = []
    failures_remaining = 0
    lock = threading.Lock()

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        with self.lock:
            self.requests.append(request)
            if self.failures_remaining:
                type(self).failures_remaining -= 1
                self.send_response(503)
                self.end_headers()
                return
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return


def _journal(tmp_path) -> tuple[Journal, Any]:
    engine = create_engine(f"sqlite:///{tmp_path / 'journal.db'}")
    journal = Journal(engine, clock=lambda: 100.0)
    with engine.begin() as connection:
        journal.append(
            connection,
            "run-1",
            "operator",
            "run.create",
            "allow",
            "private detail that must not leave the journal",
            key="run.create",
            timestamp=100.0,
        )
        journal.append(
            connection,
            "run-1",
            "builder-instance",
            "worker.started",
            "allow",
            "prompt: private prompt value",
            key="worker.started",
            timestamp=101.0,
            data={"tool_args": {"token": "private tool argument"}},
        )
        journal.append(
            connection,
            "run-1",
            "builder-instance",
            "worker.completed",
            "allow",
            "private result detail",
            key="worker.completed",
            timestamp=104.0,
            data={"duration_ms": 9000.0, "prompt": "must not be exported"},
        )
    return journal, engine


def _decoded_spans(request: ExportTraceServiceRequest) -> list[Any]:
    return [
        span
        for resource in request.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
    ]


def test_from_environment_is_disabled_without_explicit_traces_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://should-not-be-used")
    delivery = TelemetryDelivery.from_environment(journal=None)  # type: ignore[arg-type]
    assert not delivery.enabled
    assert delivery.flush_once()
    delivery.stop()


def test_otlp_http_retry_survives_restart_and_ignores_ambient_otel_settings(
    tmp_path, monkeypatch
) -> None:
    _Receiver.requests = []
    _Receiver.failures_remaining = 100
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    journal, engine = _journal(tmp_path)
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/traces"
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", endpoint)
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "lab.sentinel_password=do-not-export")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "Authorization=do-not-export")
    delivery = TelemetryDelivery.from_environment(journal)
    reopened_engine = None
    try:
        rows = journal.pending()
        expected_ids = [(row["trace_id"], row["span_id"]) for row in rows]
        assert delivery.enabled
        ambient = trace.SpanContext(
            trace_id=int("f" * 32, 16),
            span_id=int("e" * 16, 16),
            is_remote=True,
            trace_flags=trace.TraceFlags(trace.TraceFlags.SAMPLED),
        )
        token = otel_context.attach(trace.set_span_in_context(trace.NonRecordingSpan(ambient)))
        try:
            assert not delivery.flush_once()
        finally:
            otel_context.detach(token)
        assert journal.outbox_status()["pending"] == len(rows)
        assert journal.outbox_status()["last_error"] == "telemetry export failed"
        first_request_ids = [
            (span.trace_id.hex(), span.span_id.hex())
            for span in _decoded_spans(_Receiver.requests[0])
        ]
        assert first_request_ids == expected_ids

        delivery.stop()
        engine.dispose()
        reopened_engine = create_engine(f"sqlite:///{tmp_path / 'journal.db'}")
        journal = Journal(reopened_engine)
        assert len(journal.pending()) == len(rows)
        delivery = TelemetryDelivery.from_environment(journal)
        _Receiver.failures_remaining = 0
        assert delivery.flush_once()
        assert journal.outbox_status()["pending"] == 0

        delivered_request_count = len(_Receiver.requests)
        assert delivered_request_count >= 2  # OTLP may retry a 503 internally.
        assert delivery.flush_once()
        assert len(_Receiver.requests) == delivered_request_count

        successful = _Receiver.requests[-1]
        spans = _decoded_spans(successful)
        actual_ids = [(span.trace_id.hex(), span.span_id.hex()) for span in spans]
        assert actual_ids == expected_ids
        attrs = {
            item.key: getattr(item.value, item.value.WhichOneof("value"))
            for item in next(
                span
                for span in spans
                if any(
                    attribute.key == "lab.action"
                    and attribute.value.string_value == "worker.completed"
                    for attribute in span.attributes
                )
            ).attributes
        }
        assert attrs["lab.duration_ms"] == 3000.0
        encoded = successful.SerializeToString()
        assert b"private detail" not in encoded
        assert b"private prompt" not in encoded
        assert b"private tool argument" not in encoded
        assert b"must not be exported" not in encoded
        assert b"do-not-export" not in encoded
    finally:
        delivery.stop()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        if reopened_engine is not None:
            reopened_engine.dispose()
        else:
            engine.dispose()


def test_invalid_journal_chain_stops_delivery_and_records_generic_error(tmp_path) -> None:
    journal, engine = _journal(tmp_path)

    class Exporter:
        exported = False

        def export(self, spans):
            self.exported = True
            raise AssertionError("invalid history must not be exported")

        def shutdown(self) -> None:
            pass

    # Replace verification with an invalid result while retaining the real durable outbox.
    journal.verify = lambda: {"valid": False, "checked": 3, "head_hash": "bad"}  # type: ignore[method-assign]
    exporter = Exporter()
    delivery = TelemetryDelivery(journal, exporter)  # type: ignore[arg-type]
    try:
        assert not delivery.flush_once()
        assert not exporter.exported
        assert journal.outbox_status()["pending"] == 3
        assert journal.outbox_status()["last_error"] == "journal integrity verification failed"
    finally:
        delivery.stop()
        engine.dispose()
