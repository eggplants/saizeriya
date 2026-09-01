FROM debian:13-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132 AS builder

RUN --mount=type=bind,source=.,target=/app \
    --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/usr/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    <<EOF

    set -eux

    export UV_PYTHON_DOWNLOADS=manual
    uv python install --project=/app --managed-python --install-dir=/tmp/python

    (cd /tmp/python/* && tar -cf- .) | (cd /usr/local && tar -xf-)
    rm -r /tmp/python

    export UV_PROJECT_ENVIRONMENT=/usr/local
    uv sync --project=/app --frozen --compile-bytecode --link-mode=copy --no-dev --no-editable --no-managed-python
EOF

FROM gcr.io/distroless/cc-debian12:nonroot@sha256:e2d29aec8061843706b7e484c444f78fafb05bfe47745505252b1769a05d14f1

COPY --from=builder /usr/local /usr/local

USER nonroot

ENTRYPOINT ["/usr/local/bin/saizeriya"]
