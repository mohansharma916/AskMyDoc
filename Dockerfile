FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models

WORKDIR /app

# CPU-only PyTorch keeps the image far smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY pyproject.toml README.md ./
COPY src ./src
# Editable install so settings resolve prompts/ and data/ relative to /app.
RUN pip install -e .

COPY prompts ./prompts
COPY eval/corpus ./eval/corpus

EXPOSE 8000
CMD ["uvicorn", "askdocs.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
