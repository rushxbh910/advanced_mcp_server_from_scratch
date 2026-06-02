FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

# Install CPU-only PyTorch first, then sync everything else without overwriting it.
# This prevents sentence-transformers from pulling in 3GB of CUDA GPU libraries.
RUN uv venv && \
    uv pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    uv sync --frozen --no-dev --no-install-package torch

COPY . .

# Pre-download the embedding model at build time to eliminate cold-start latency
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000

CMD ["uv", "run", "python", "main.py"]
