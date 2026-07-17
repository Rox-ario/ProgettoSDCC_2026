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

# Blocco 5: Pre-download dei pesi dei modelli DeepFace durante la build
# In cloud (ACI), il container parte senza cache locale (~/.deepface/weights/).
# Senza questo step, DeepFace tenta di scaricare i modelli a runtime e fallisce
# silenziosamente (enforce_detection=False), restituendo lista vuota per ogni frame.
RUN python -c "\
import os, numpy as np, cv2; \
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'; \
img = np.zeros((100,100,3), dtype=np.uint8); \
cv2.imwrite('/tmp/dummy.jpg', img); \
from deepface import DeepFace; \
DeepFace.analyze('/tmp/dummy.jpg', actions=['emotion'], enforce_detection=False, detector_backend='opencv'); \
print('Modelli DeepFace scaricati con successo.')" || echo "Pre-download tentato (eventuali errori di rilevamento volto su dummy image sono normali)."

# Comando di avvio del Worker
CMD ["python", "worker.py"]