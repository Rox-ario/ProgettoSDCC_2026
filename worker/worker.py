import os
# Silenziamo i log nativi di TensorFlow prima di importare DeepFace
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import time
import json
import logging
import tempfile
import shutil
from dotenv import load_dotenv
import cv2
from azure.storage.queue import QueueClient
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableClient, UpdateMode
from azure.core.exceptions import HttpResponseError
from datetime import datetime, timezone

# Importazione del motore AI raccomandato dal Docente
from deepface import DeepFace

# Configurazione del Logging Applicativo chiaro e pulito
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("azure.core.pipeline").setLevel(logging.WARNING)
logging.getLogger("azure.storage").setLevel(logging.WARNING)

def process_video_frames(video_path, output_dir, interval_seconds=1):
    """Apre il video ed estrae i frame a intervalli regolari calcolati sui FPS."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Impossibile aprire il file video locale con OpenCV.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(f"[OpenCV] Video caricato. FPS: {fps:.2f} | Frame Totali: {total_frames}")

    # Calcolo matematico dello step per svincolarsi dal framerate nativo
    frame_step = max(1, int(fps * interval_seconds))
    extracted_count = 0
    frame_id = 0

    while True:
        if frame_id % frame_step == 0:
            ret, frame = cap.read()  # Decodifica effettiva solo del frame target
            if not ret:
                break
            frame_filename = f"frame_{extracted_count:04d}.jpg"
            frame_output_path = os.path.join(output_dir, frame_filename)
            cv2.imwrite(frame_output_path, frame)
            extracted_count += 1
        else:
            ret = cap.grab()  # Salto veloce del frame in memoria senza decodifica grafica
            if not ret:
                break
        frame_id += 1

    cap.release()
    logger.info(f"[OpenCV] Estrazione completata: {extracted_count} frame pronti in memoria locale.")
    return extracted_count

def main():
    load_dotenv()

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    queue_name = os.getenv("QUEUE_NAME", "video-processing-queue")
    container_name = os.getenv("BLOB_CONTAINER_NAME", "multimedia-contents")

    if not connection_string:
        logger.error("AZURE_STORAGE_CONNECTION_STRING non configurata nel file .env")
        return

    # Inizializzazione dei Client SDK di Azure Storage (Azurite locale)
    queue_client = QueueClient.from_connection_string(conn_str=connection_string, queue_name=queue_name)
    blob_service_client = BlobServiceClient.from_connection_string(conn_str=connection_string)

    logger.info(f"=== Worker AI in ascolto sulla coda '{queue_name}' ===")

    # Connessione alla Tabella Storage per la persistenza dei risultati (Fase 3.4)
    connection_string = "UseDevelopmentStorage=true"
    table_name = "MediaMetadata"
    table_client = TableClient.from_connection_string(conn_str=connection_string, table_name=table_name)

    last_heartbeat = 0
    HEARTBEAT_INTERVAL = 5  # Il worker emette un battito ogni 5 secondi

    while True:
        # ─── HEARTBEAT PATTERN (Battito Cardiaco) ─────────────
        try:
            current_time = time.time()
            if current_time - last_heartbeat > HEARTBEAT_INTERVAL:
                heartbeat_entity = {
                    "PartitionKey": "SYSTEM",
                    "RowKey": "WORKER_HEARTBEAT",
                    "LastSeen": datetime.now(timezone.utc).isoformat()
                }
                table_client.upsert_entity(entity=heartbeat_entity)
                last_heartbeat = current_time
        except Exception as e:
            logger.warning(f"Impossibile inviare heartbeat: {e}")
        try:
            # Polling asincrono con Lock di Visibility a 5 minuti
            messages = queue_client.receive_messages(max_messages=1, visibility_timeout=300)
            message_list = list(messages)

            if not message_list:
                time.sleep(5)  # Backoff incrementale passivo
                continue

            message = message_list[0]
            logger.info(f"--- Nuovo Task Rilevato! Message ID: {message.id} ---")

            # Gestione della Poison Pill cumulativa
            if message.dequeue_count > 5:
                logger.critical(f"Poison Pill rilevata! Rimozione forzata del messaggio ID: {message.id}")
                queue_client.delete_message(message.id, message.pop_receipt)
                continue

            # Allocazione dello storage temporaneo effimero
            base_temp_dir = tempfile.mkdtemp(prefix="ai_worker_")
            frames_dir = os.path.join(base_temp_dir, "extracted_frames")
            os.makedirs(frames_dir, exist_ok=True)

            try:
                # 1. Parsing sicuro dei metadati del task
                try:
                    payload = json.loads(message.content)

                    current_subject_id = payload["PartitionKey"]
                    current_task_id = payload["RowKey"]
                    blob_target = payload["blob_target"]

                except (json.JSONDecodeError, KeyError) as json_err:
                    logger.critical(f"Poison Pill Strutturale! Manca una chiave del contratto JSON. Errore: {json_err}")
                    queue_client.delete_message(message.id, message.pop_receipt)
                    continue

                # 2. Download del file binario dal Cloud Blob Storage locale
                local_file_path = os.path.join(base_temp_dir, blob_target)
                logger.info(f"Scaricamento del blob '{blob_target}' in corso...")

                blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_target)
                with open(local_file_path, "wb") as download_file:
                    download_file.write(blob_client.download_blob().readall())
                logger.info("Download completato con successo.")

                # 3. Pipeline di scomposizione multimediale
                _, file_extension = os.path.splitext(blob_target.lower())
                if file_extension in ['.mp4', '.avi', '.mov', '.mkv']:
                    process_video_frames(local_file_path, frames_dir, interval_seconds=1)
                elif file_extension in ['.jpg', '.jpeg', '.png']:
                    shutil.copy(local_file_path, os.path.join(frames_dir, "frame_0000.jpg"))
                else:
                    logger.error(f"Formato '{file_extension}' non supportato. Scarto il task.")
                    queue_client.delete_message(message.id, message.pop_receipt)
                    continue

                # 4. FASE 3.3: INFERENZA AI TRAMITE DEEPFACE LOCALE
                logger.info("Inizializzazione DeepFace. Avvio analisi della sequenza emotiva...")

                analysis_records = []
                frame_files = sorted(os.listdir(frames_dir))

                for idx, frame_file in enumerate(frame_files):
                    frame_path = os.path.join(frames_dir, frame_file)

                    try:
                        # Ottimizzazione: eseguiamo solo 'emotion'. enforce_detection=False evita crash protetti.
                        predictions = DeepFace.analyze(img_path=frame_path, actions=['emotion'], enforce_detection=False)

                        # DeepFace restituisce una lista di dizionari (uno per ogni volto rilevato nel frame)
                        for face_index, face_data in enumerate(predictions):
                            if 'emotion' in face_data:
                                record = {
                                    "timestamp_second": idx,
                                    "face_id": face_index,
                                    "dominant_emotion": face_data['dominant_emotion'],
                                    "confidence": round(face_data.get('face_confidence', 0), 4),
                                    # Punteggi percentuali grezzi di tutte le emozioni
                                    "metrics": face_data['emotion']
                                }
                                analysis_records.append(record)
                                logger.info(f" -> Frame {frame_file} (Secondo {idx}): Volto {face_index} -> Emozione: {face_data['dominant_emotion'].upper()} (Conf: {record['confidence']})")

                    except Exception as single_frame_err:
                        logger.error(f"Impossibile analizzare il frame {frame_file}: {single_frame_err}")

                logger.info(f"Analisi AI conclusa. Estratti {len(analysis_records)} record emotivi totali.")

                logger.info("[Placeholder] Pronto per la persistenza NoSQL su Azure Table Storage...")
                # 1. Serializzazione: Convertiamo la lista di dizionari in una stringa JSON
                results_json = json.dumps(analysis_records)

                # 3. Preparazione dell'entità per il Merge
                entity_update = {
                    "PartitionKey": current_subject_id,
                    "RowKey": current_task_id,
                    "Processed": True,
                    "AnalysisResults": results_json
                }

                try:
                    # 4. UpdateMode.MERGE aggiorna solo i campi specificati, lasciando intatti i metadati originali
                    table_client.update_entity(entity=entity_update, mode=UpdateMode.MERGE)
                    print(f"[OK] Risultati salvati in Table Storage per il task: {current_task_id}")

                    # 5. SOLO ORA eliminiamo il messaggio dalla coda.
                    # Se il salvataggio sul DB fallisce, non cancelliamo il messaggio,
                    # così la coda ce lo riproporrà in futuro (At-Least-Once Delivery).
                    queue_client.delete_message(message.id, message.pop_receipt)
                    print(f"[OK] Task {current_task_id} rimosso dalla coda.")

                except HttpResponseError as e:
                    print(f"[ERRORE] Impossibile aggiornare la Table Storage: {e}")
                    # Il messaggio NON viene cancellato e tornerà visibile nella coda tra 300 secondi

            except Exception as task_err:
                logger.error(f"Errore critico durante la lavorazione del Task: {task_err}")
                logger.info("Il messaggio non viene eliminato e tornerà disponibile nella coda.")

            finally:
                # 6. Pulizia radicale del file system temporaneo effimero (Stateless constraint)
                if os.path.exists(base_temp_dir):
                    shutil.rmtree(base_temp_dir)
                    logger.info("Directory temporanea locale rimossa. Stato effimero azzerato.")

        except Exception as queue_err:
            logger.error(f"Errore di comunicazione con Azure Queue infrastructure: {queue_err}")
            time.sleep(10)

if __name__ == "__main__":
    main()