FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 WHYBOT_MODELS_DIR=/app/models
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY whybot ./whybot
COPY bench ./bench
COPY results ./results
# Download the two small ONNX models at build time so the container starts fast.
RUN python -c "from pathlib import Path; from whybot.retrieval.onnx_models import Embedder, Reranker; Embedder(Path('/app/models')); Reranker(Path('/app/models'))"
EXPOSE 8000
CMD ["uvicorn", "whybot.api:app", "--host", "0.0.0.0", "--port", "8000"]
