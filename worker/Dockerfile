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
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Blocco 3: Installazione delle librerie Python
# Installiamo prima le dipendenze, poi forziamo opencv-headless per sovrascrivere
# qualsiasi versione piena di opencv che deepface potrebbe installare come dipendenza.
COPY requirements-worker.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-worker.txt && \
    pip install --no-cache-dir --force-reinstall opencv-python-headless==4.9.0.80 && \
    pip install --no-cache-dir --force-reinstall "numpy==1.26.4"

# Blocco 4: Copia del codice sorgente
COPY . .

# Comando di avvio del Worker
CMD ["python", "worker.py"]