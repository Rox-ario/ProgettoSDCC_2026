# Blocco 1: Immagine di base ottimizzata e compatibile con TensorFlow 2.21
FROM python:3.11-slim

# Evita che Python scriva file .pyc e forza l'output dei log sulla console
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Imposta la directory di lavoro dentro il container
WORKDIR /app

# Blocco 2: Installazione dipendenze di sistema necessarie per OpenCV
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Blocco 3: Installazione delle librerie Python
COPY requirements-worker.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-worker.txt

# Blocco 4: Copia del codice sorgente
COPY . .

# Comando di avvio del Worker
CMD ["python", "worker.py"]