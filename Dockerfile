FROM python:3.12-slim

ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.version="$APP_VERSION"

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir fastmcp python-docx pdfplumber watchdog

COPY resume_mcp_server/ ./resume_mcp_server/
RUN pip install --no-cache-dir -e .

RUN useradd -m -u 1000 appuser && mkdir -p /resumes && chown appuser:appuser /resumes

ENV RESUME_DIR=/resumes
ENV FASTMCP_TRANSPORT=stdio

VOLUME ["/resumes"]

USER appuser

CMD ["resume-mcp-server"]
