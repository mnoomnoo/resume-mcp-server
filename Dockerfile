FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir fastmcp python-docx pdfplumber hatchling watchdog

COPY resume_mcp_server/ ./resume_mcp_server/
RUN pip install --no-cache-dir -e .

ENV RESUME_DIR=/resumes
VOLUME ["/resumes"]

CMD ["resume-mcp-server"]
