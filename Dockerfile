FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Install deps from lock file before copying app code (layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application source
COPY . .

# Pre-download the embedding model at build time to eliminate cold-start latency
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000

CMD ["uv", "run", "python", "main.py"]
