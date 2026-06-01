import os
import time
import json
import logging
import tempfile
import shutil
from dotenv import load_dotenv
from azure.storage.queue import QueueClient

# 1. Configurazione del Root Logger a livello INFO per la nostra applicazione
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. RISOLUZIONE INQUINAMENTO LOG (Logger Pollution)
# Intercettiamo i logger interni dell'SDK Azure e alziamo la soglia a WARNING.
# In questo modo tutto il rumore delle chiamate HTTP andate a buon fine sparirà.
logging.getLogger("azure.core.pipeline").setLevel(logging.WARNING)
logging.getLogger("azure.storage").setLevel(logging.WARNING)

# Soglia oltre la quale un messaggio è considerato "avvelenato" e va eliminato
MAX_DEQUEUE_COUNT = 5

# Visibility timeout generoso: deve coprire il caso peggiore
# (download blob + estrazione frame + N chiamate AI)
VISIBILITY_TIMEOUT_SECONDS = 300


def main():
    load_dotenv()

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    queue_name = os.getenv("QUEUE_NAME", "video-processing-queue")

    if not connection_string:
        logger.error("AZURE_STORAGE_CONNECTION_STRING non trovata nel file .env")
        return

    queue_client = QueueClient.from_connection_string(
        conn_str=connection_string,
        queue_name=queue_name
    )

    logger.info(f"Worker in ascolto sulla coda '{queue_name}'...")

    while True:
        try:
            messages = queue_client.receive_messages(
                max_messages=1,
                visibility_timeout=VISIBILITY_TIMEOUT_SECONDS
            )
            message_list = list(messages)

            if not message_list:
                time.sleep(5)
                continue

            message = message_list[0]
            logger.info(f"Ricevuto messaggio ID: {message.id} "
                        f"(tentativo #{message.dequeue_count})")

            # Gestione Poison Pill: se il messaggio è stato prelevato
            # troppe volte senza successo, è quasi certamente corrotto.
            # Eliminarlo è la scelta corretta per sbloccare la coda.
            if message.dequeue_count > MAX_DEQUEUE_COUNT:
                logger.warning(
                    f"Messaggio {message.id} superato il limite di "
                    f"{MAX_DEQUEUE_COUNT} tentativi. Eliminato come Poison Pill."
                )
                queue_client.delete_message(message.id, message.pop_receipt)
                continue

            temp_dir = tempfile.mkdtemp(prefix="ai_worker_")
            logger.info(f"Directory di lavoro temporanea: {temp_dir}")

            try:
                payload = json.loads(message.content)
                logger.info(f"Payload: {json.dumps(payload, indent=2)}")

                # --- QUI: download blob, estrazione frame, chiamate AI ---
                time.sleep(2)  # Simulazione
                logger.info("Elaborazione simulata completata.")

                queue_client.delete_message(message.id, message.pop_receipt)
                logger.info("Messaggio eliminato dalla coda (acknowledge).")

            except json.JSONDecodeError as e:
                logger.error(f"JSON non valido: {e}. "
                             f"Il messaggio tornerà visibile dopo il timeout.")
                # Non eliminiamo: il dequeue_count aumenterà,
                # e verrà rimosso come Poison Pill al prossimo ciclo.

            except Exception as e:
                logger.error(f"Errore durante l'elaborazione: {e}")
                # Stesso ragionamento: non eliminiamo, lasciamo che
                # il sistema di retry naturale di Azure faccia il suo lavoro.

            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.info(f"Directory temporanea rimossa: {temp_dir}")

        except Exception as e:
            logger.error(f"Errore critico di connessione: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()