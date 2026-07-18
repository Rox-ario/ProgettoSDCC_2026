import json
import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient
from azure.data.tables import TableServiceClient, TableEntity
from azure.core.exceptions import ResourceExistsError
import uuid

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME", "multimedia-contents")
QUEUE_NAME = os.getenv("QUEUE_NAME", "video-processing-queue")
TABLE_NAME = os.getenv("TABLE_NAME", "MediaMetadata")

def initialize_azure_resources():
    if not CONNECTION_STRING:
        print("Errore: AZURE_STORAGE_CONNECTION_STRING non trovata nel file .env!")
        return

    print("=== Inizio Inizializzazione Risorse Azure ===")

    try:
        blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        container_client.create_container()
        print(f"[OK] Blob Container '{BLOB_CONTAINER_NAME}' creato con successo.")
    except ResourceExistsError:
        print(f"[INFO] Blob Container '{BLOB_CONTAINER_NAME}' già esistente.")
    except Exception as e:
        print(f"[ERRORE] Impossibile creare il Blob Container: {e}")

    try:
        queue_service_client = QueueServiceClient.from_connection_string(CONNECTION_STRING)
        queue_client = queue_service_client.get_queue_client(QUEUE_NAME)
        queue_client.create_queue()
        print(f"[OK] Coda '{QUEUE_NAME}' creata con successo.")
    except ResourceExistsError:
        print(f"[INFO] Coda '{QUEUE_NAME}' già esistente.")
    except Exception as e:
        print(f"[ERRORE] Impossibile creare la Coda: {e}")

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
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)

    ext = os.path.splitext(original_filename)[1]
    unique_id = str(uuid.uuid4())
    unique_blob_name = f"{unique_id}{ext}"

    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=unique_blob_name)
    blob_client.upload_blob(file_bytes, overwrite=True)

    return unique_blob_name, unique_id


def save_metadata_to_table(subject_id, unique_id, metadata):
    table_service_client = TableServiceClient.from_connection_string(conn_str=CONNECTION_STRING)
    table_client = table_service_client.get_table_client(table_name=TABLE_NAME)

    entity = TableEntity()
    entity["PartitionKey"] = subject_id
    entity["RowKey"] = unique_id

    for key, value in metadata.items():
        entity[key] = value

    table_client.create_entity(entity=entity)

def send_message_to_queue(unique_id, blob_name, partition_key):
    queue_service_client = QueueServiceClient.from_connection_string(CONNECTION_STRING)
    queue_client = queue_service_client.get_queue_client(QUEUE_NAME)

    message_content = {
        "task_id": unique_id,
        "blob_target": blob_name,
        "PartitionKey": partition_key,
        "RowKey": unique_id
    }

    json_message = json.dumps(message_content)

    queue_client.send_message(json_message)
    print(f"[OK] Messaggio di notifica inviato alla coda per il task: {unique_id}")

if __name__ == "__main__":
    initialize_azure_resources()