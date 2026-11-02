FROM debian:13-slim@sha256:f6b08b09a05725f9431502d3b5714f5c4576e82c1a84fa1debe0c24a7e0c3ec4 AS builder

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

FROM gcr.io/distroless/cc-debian12:nonroot@sha256:9dac0a79194e45a7da0158a9c6da57b217585af0786db3845d1f0ec1a0dd182f

COPY --from=builder /usr/local /usr/local

USER nonroot

ENTRYPOINT ["/usr/local/bin/saizeriya"]
