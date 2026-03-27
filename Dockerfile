# NSP Plugin - Production Dockerfile
# Imagem otimizada para servir API de predição

FROM python:3.11-slim

# Metadata
LABEL maintainer="NSP Plugin" \
      description="AI-powered preset prediction API for Lightroom" \
      version="2.0"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    libopencv-dev \
    libraw-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Criar diretórios
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY services/ ./services/
COPY train/ ./train/
COPY models/ ./models/
COPY data/ ./data/
COPY scripts/ ./scripts/

# Criar usuário não-root
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expor porta do servidor
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5001/health', timeout=5)" || exit 1

# Comando de início
CMD ["python", "-m", "uvicorn", "services.server:app", "--host", "0.0.0.0", "--port", "5001", "--workers", "4"]
