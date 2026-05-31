import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError

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

if __name__ == "__main__":
    # Consente l'esecuzione diretta del file per testare l'infrastruttura locale
    initialize_azure_resources()