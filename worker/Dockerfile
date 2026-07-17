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
COPY requirements-worker.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-worker.txt

# Blocco 4: Copia del codice sorgente
COPY . .

# Blocco 5: Pre-download dei pesi del modello DeepFace durante la build
# Usa DeepFace.build_model("Emotion") per scaricare i pesi ESPLICITAMENTE,
# senza dipendere dal rilevamento di un volto in un'immagine dummy.
# Questo garantisce che i pesi siano disponibili nell'immagine Docker in ACI.
RUN python -c "\
import os; \
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'; \
print('Scaricamento modello Emotion...'); \
from deepface import DeepFace; \
DeepFace.build_model('Emotion'); \
print('[OK] Modello Emotion scaricato e pronto.'); \
import cv2; \
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'); \
print('[OK] Cascade OpenCV caricato correttamente.')"

# Comando di avvio del Worker
CMD ["python", "worker.py"]