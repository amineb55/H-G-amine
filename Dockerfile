# Build stage: resolve dependencies into a self-contained prefix.
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .

# Installed under /install so the runtime image takes the packages without
# pip, its caches, or any build leftovers.
RUN pip install --prefix=/install -r requirements.txt


# Runtime stage.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

# ffmpeg is bundled inside the imageio-ffmpeg wheel as a ~78 MB statically
# linked binary, so the slim image needs no apt package and nothing is
# downloaded at run time. The copy preserves its executable bit.
COPY --from=builder /install /usr/local

WORKDIR /app
COPY app ./app
COPY templates ./templates
COPY static ./static

# Scratch space for uploads, which are deleted as soon as a job ends.
RUN mkdir -p /app/data/uploads \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# The platform supplies PORT; the shell form expands it, and 8080 is the
# fallback for a plain `docker run`.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
