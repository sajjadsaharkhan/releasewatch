FROM python:3.12-slim
WORKDIR /app

# Install build tools before any package installation
RUN pip install --no-cache-dir setuptools wheel

COPY pyproject.toml .
# Install all dependencies (non-editable); source is COPY-ed in next step
RUN pip install --no-cache-dir -e .


COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
