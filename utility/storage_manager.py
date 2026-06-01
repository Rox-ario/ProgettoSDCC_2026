import json
import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient
from azure.data.tables import TableServiceClient, TableEntity
from azure.core.exceptions import ResourceExistsError
import uuid

# Blocco 1: Caricamento delle variabili d'ambiente dal file .env
load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
# Definiamo dei valori di fallback nel caso in cui non fossero presenti nel .env
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME", "multimedia-contents")
QUEUE_NAME = os.getenv("QUEUE_NAME", "video-processing-queue")
TABLE_NAME = os.getenv("TABLE_NAME", "MetadataRegistry")

def initialize_azure_resources():
    """
    Inizializza le risorse di storage (Blob, Queue, Table) su Azurite/Azure
    se non sono già esistenti.
    """
    if not CONNECTION_STRING:
        print("Errore: AZURE_STORAGE_CONNECTION_STRING non trovata nel file .env!")
        return

    print("=== Inizio Inizializzazione Risorse Azure ===")

    # ---------------------------------------------------------
    # Blocco 2 & 3: Configurazione e creazione Blob Storage
    # ---------------------------------------------------------
    try:
        blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        container_client.create_container()
        print(f"[OK] Blob Container '{BLOB_CONTAINER_NAME}' creato con successo.")
    except ResourceExistsError:
        print(f"[INFO] Blob Container '{BLOB_CONTAINER_NAME}' già esistente.")
    except Exception as e:
        print(f"[ERRORE] Impossibile creare il Blob Container: {e}")

    # ---------------------------------------------------------
    # Blocco 2 & 3: Configurazione e creazione Queue Storage
    # ---------------------------------------------------------
    try:
        queue_service_client = QueueServiceClient.from_connection_string(CONNECTION_STRING)
        queue_client = queue_service_client.get_queue_client(QUEUE_NAME)
        queue_client.create_queue()
        print(f"[OK] Coda '{QUEUE_NAME}' creata con successo.")
    except ResourceExistsError:
        print(f"[INFO] Coda '{QUEUE_NAME}' già esistente.")
    except Exception as e:
        print(f"[ERRORE] Impossibile creare la Coda: {e}")

    # ---------------------------------------------------------
    # Blocco 2 & 3: Configurazione e creazione Table Storage
    # ---------------------------------------------------------
    try:
        table_service_client = TableServiceClient.from_connection_string(conn_str=CONNECTION_STRING)
        table_client = table_service_client.get_table_client(table_name=TABLE_NAME)
        table_client.create_table()
        print(f"[OK] Tabella '{TABLE_NAME}' creata con successo.")
    except ResourceExistsError:
        print(f"[INFO] Tabella '{TABLE_NAME}' già esistente.")
    except Exception as e:
        print(f"[ERRORE] Impossibile creare la Tabella: {e}")

    print("=== Fine Inizializzazione Risorse Azure ===")

def upload_file_to_blob(file_bytes, original_filename):
    """
    Genera un ID univoco, rinomina il file e lo carica nel Blob Storage.
    Ritorna: (string: unique_blob_name, string: unique_id)
    """
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)

    # Blocco Logico 1: Generazione ID univoco mantenendo l'estensione originale
    ext = os.path.splitext(original_filename)[1] # Es: .mp4 o .png
    unique_id = str(uuid.uuid4())
    unique_blob_name = f"{unique_id}{ext}"

    # Blocco Logico 2: Connessione al client del blob e upload dei byte
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=unique_blob_name)
    blob_client.upload_blob(file_bytes, overwrite=True)

    return unique_blob_name, unique_id


def save_metadata_to_table(subject_id, unique_id, metadata):
    """
    Salva i metadati strutturati su Azure Table Storage.
    Mappa il subject_id come PartitionKey e l'unique_id come RowKey.
    """
    table_service_client = TableServiceClient.from_connection_string(conn_str=CONNECTION_STRING)
    table_client = table_service_client.get_table_client(table_name=TABLE_NAME)

    # Blocco Logico 3: Costruzione dell'entità NoSQL rispettando i vincoli di Azure
    entity = TableEntity()
    entity["PartitionKey"] = subject_id
    entity["RowKey"] = unique_id

    # Popoliamo l'entità con gli altri metadati passati come dizionario
    for key, value in metadata.items():
        entity[key] = value

    # Inseriamo l'entità nel Table Storage
    table_client.create_entity(entity=entity)

def send_message_to_queue(unique_id, blob_name):
    """
    Invia un messaggio in formato JSON alla coda di Azure Queue Storage
    per notificare il Worker asincrono.
    """
    queue_service_client = QueueServiceClient.from_connection_string(CONNECTION_STRING)
    queue_client = queue_service_client.get_queue_client(QUEUE_NAME)

    # Blocco Logico 1: Creazione del payload minimo in formato JSON
    message_content = {
        "task_id": unique_id,
        "blob_target": blob_name
    }

    # Trasformiamo il dizionario in stringa di testo
    json_message = json.dumps(message_content)

    # Blocco Logico 2: Invio del messaggio alla coda
    queue_client.send_message(json_message)
    print(f"[OK] Messaggio di notifica inviato alla coda per il task: {unique_id}")

if __name__ == "__main__":
    # Consente l'esecuzione diretta del file per testare l'infrastruttura locale
    initialize_azure_resources()