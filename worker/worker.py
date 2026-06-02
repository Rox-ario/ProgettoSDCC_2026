import os
import time
import json
import logging
import tempfile
import shutil
from dotenv import load_dotenv
import cv2  # OpenCV Headless
from azure.storage.queue import QueueClient
from azure.storage.blob import BlobServiceClient

# Configurazione Logging coerente (Zittiamo l'SDK di Azure)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("azure.core.pipeline").setLevel(logging.WARNING)
logging.getLogger("azure.storage").setLevel(logging.WARNING)

def process_video_frames(video_path, output_dir, interval_seconds=1):
    """Apre il video ed estrae i frame a intervalli regolari di secondi."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Impossibile aprire il file video con OpenCV.")

    # Recuperiamo dinamicamente il Frame Rate del video
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(f"Video aperto correttamente. FPS: {fps} | Frame Totali: {total_frames}")

    # Calcoliamo quanti frame saltare per rispettare l'intervallo in secondi
    frame_step = max(1, int(fps * interval_seconds))
    extracted_count = 0
    frame_number = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_number % frame_step == 0:
            frame_filename = f"frame_{extracted_count:04d}.jpg"
            cv2.imwrite(os.path.join(output_dir, frame_filename), frame)
            extracted_count += 1

        frame_number += 1

    cap.release()
    logger.info(f"Estrazione completata. Estratti {extracted_count} frame nella directory temporanea.")
    return extracted_count

def main():
    load_dotenv()

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    queue_name = os.getenv("QUEUE_NAME", "video-processing-queue")
    container_name = os.getenv("BLOB_CONTAINER_NAME", "multimedia-contents")

    if not connection_string:
        logger.error("AZURE_STORAGE_CONNECTION_STRING non trovata nel file .env")
        return

    # Inizializzazione Client Azure Storage
    queue_client = QueueClient.from_connection_string(conn_str=connection_string, queue_name=queue_name)
    blob_service_client = BlobServiceClient.from_connection_string(conn_str=connection_string)

    logger.info(f"Worker in ascolto (Fase 3.2). Coda: '{queue_name}' | Container: '{container_name}'")

    while True:
        try:
            messages = queue_client.receive_messages(max_messages=1, visibility_timeout=300)
            message_list = list(messages)

            if not message_list:
                time.sleep(5)
                continue

            message = message_list[0]
            logger.info(f"Preso in carico messaggio ID: {message.id}")

            if message.dequeue_count > 5:
                logger.critical(f"Rilevata Poison Pill! Rimozo messaggio ID: {message.id}")
                queue_client.delete_message(message.id, message.pop_receipt)
                continue

            # Creazione della directory temporanea ephemera di lavoro
            base_temp_dir = tempfile.mkdtemp(prefix="ai_worker_")
            # Sottocartella specifica dove isoleremo solo i frame pronti per l'AI
            frames_dir = os.path.join(base_temp_dir, "extracted_frames")
            os.makedirs(frames_dir, exist_ok=True)

            try:
                # 1. Decodifica del JSON proveniente dalla coda
                try:
                    payload = json.loads(message.content)
                    blob_target = payload.get("blob_target")
                    if not blob_target:
                        raise KeyError("Chiave 'blob_target' mancante nel payload.")
                except (json.JSONDecodeError, KeyError) as json_err:
                    logger.critical(f"Poison Pill Strutturale. Errore parsing: {json_err}")
                    queue_client.delete_message(message.id, message.pop_receipt)
                    continue

                # 2. DOWNLOAD DEL FILE DAL BLOB STORAGE
                local_file_path = os.path.join(base_temp_dir, blob_target)
                logger.info(f"Scaricamento del blob '{blob_target}' dal container '{container_name}'...")

                blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_target)

                with open(local_file_path, "wb") as download_file:
                    download_stream = blob_client.download_blob()
                    download_file.write(download_stream.readall())
                logger.info(f"File scaricato localmente in: {local_file_path}")

                # 3. DISCRIMINAZIONE TIPO FILE ED ESTRAZIONE FRAME
                _, file_extension = os.path.splitext(blob_target.lower())
                video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
                image_extensions = ['.jpg', '.jpeg', '.png']

                if file_extension in video_extensions:
                    logger.info("Rilevato file Video. Avvio estrazione frame ad intervalli regolari...")
                    # Estraiamo 1 frame ogni 1 secondo (modificabile se necessario)
                    num_frames = process_video_frames(local_file_path, frames_dir, interval_seconds=1)
                elif file_extension in image_extensions:
                    logger.info("Rilevato file Immagine singola. Copia diretta nella cartella di processing.")
                    # Se è un'immagine singola, la copiamo semplicemente nella cartella dei frame per uniformità
                    shutil.copy(local_file_path, os.path.join(frames_dir, "frame_0000.jpg"))
                    num_frames = 1
                else:
                    logger.error(f"Formato file '{file_extension}' non supportato dai requisiti di progetto.")
                    queue_client.delete_message(message.id, message.pop_receipt)
                    continue

                # --- QUI IN FUTURO (Fase 3.3) CHIAMEREMO LE API DI AZURE AI FACENDO UN LOOP DEI FILE IN 'frames_dir' ---
                logger.info(f"Fase 3.2 completata con successo. {num_frames} immagini pronte in {frames_dir}.")

                # Rimuoviamo il messaggio dalla coda perché questa fase intermedia è andata a buon fine
                queue_client.delete_message(message.id, message.pop_receipt)
                logger.info(f"Messaggio {message.id} rimosso con successo.")

            except Exception as proc_err:
                logger.error(f"Errore di elaborazione transitorio: {proc_err}")
                logger.info("Il messaggio tornerà visibile allo scadere del timeout.")

            finally:
                # Pulizia totale e tassativa del file system locale
                if os.path.exists(base_temp_dir):
                    shutil.rmtree(base_temp_dir)
                    logger.info("Pulizia della directory temporanea completata.")

        except Exception as queue_err:
            logger.error(f"Errore interazione Storage: {queue_err}")
            time.sleep(10)

if __name__ == "__main__":
    main()