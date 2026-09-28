FROM python:3.11-slim AS layout
RUN mkdir -p /var/lib/otelcol && chown 10001:10001 /var/lib/otelcol

FROM otel/opentelemetry-collector-contrib:0.161.0
COPY --from=layout --chown=10001:10001 /var/lib/otelcol /var/lib/otelcol
USER 10001:10001
