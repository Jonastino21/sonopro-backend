FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# PyTorch CPU d'abord (évite de télécharger la version GPU)
RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    torchaudio==2.2.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-télécharge le modèle DeepFilterNet au build (pas au runtime)
RUN git init && python -c "from df.enhance import init_df; init_df()" && rm -rf .git

COPY . .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]