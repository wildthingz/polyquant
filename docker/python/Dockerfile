FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Matching versions from docs/DEPLOYMENT.md
RUN pip install --no-cache-dir \
    xgboost==2.0.3 \
    scikit-learn==1.4.0 \
    onnx==1.15.0 \
    onnxruntime==1.17.1 \
    skl2onnx==1.16.0 \
    pandas==2.2.0 \
    numpy==1.26.3 \
    psycopg2-binary==2.9.9

CMD ["python3"]
