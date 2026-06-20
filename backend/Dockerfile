FROM python:3.12-slim
WORKDIR /app

# Install build tools before any package installation
RUN pip install --no-cache-dir setuptools wheel

COPY pyproject.toml .
# Install all dependencies (non-editable); source is COPY-ed in next step
RUN pip install --no-cache-dir -e .

# Pre-download the local embedding model so the first request is instant
RUN python -c "from fastembed import TextEmbedding; list(TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2').embed(['warmup']))"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
