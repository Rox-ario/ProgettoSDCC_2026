# Orfeo — Emotion Analysis Platform
**Sistemi Distribuiti e Cloud Computing · A.A. 2025/2026**

## Descrizione
Orfeo è una piattaforma cloud-native per l'analisi emotiva di file multimediali (video e immagini). Il sistema acquisisce un file, lo invia a un worker AI basato su **DeepFace** per l'estrazione delle emozioni frame per frame, e visualizza i risultati attraverso una dashboard interattiva costruita con **Streamlit**.

## Architettura

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────────────┐
│  Streamlit  │──────▶│  Azure Queue     │──────▶│  Worker AI (ACI)    │
│  Web App    │       │  Storage         │       │  DeepFace + TF 2.21 │
│  (App Svc)  │       └──────────────────┘       └──────────┬──────────┘
│             │                                             │
│  Dashboard  │◀────────────────────────────────────────────┤
└─────────────┘       ┌──────────────────┐       ┌──────────▼──────────┐
                      │  Azure Table     │◀──────│  Azure Blob         │
                      │  Storage         │       │  Storage            │
                      │  (Metadata+Ref)  │       │  (Video + Results)  │
                      └──────────────────┘       └─────────────────────┘
```

### Componenti

| Componente | Tecnologia | Hosting |
|---|---|---|
| Web App Frontend | Streamlit (Python) | Azure App Service |
| Worker AI | DeepFace + TensorFlow 2.21 | Azure Container Instances |
| Message Broker | Azure Queue Storage | Azure Storage Account |
| Database NoSQL | Azure Table Storage | Azure Storage Account |
| Object Storage | Azure Blob Storage | Azure Storage Account |

### Pattern Architetturali implementati
- **Competing Consumers**: il worker polling sulla coda con visibility lock
- **Claim Check**: i risultati JSON pesanti vengono salvati su Blob; la Table contiene solo il riferimento (`blob_ref`)
- **At-Least-Once Delivery**: il messaggio in coda viene eliminato solo dopo il salvataggio avvenuto con successo
- **Heartbeat**: il worker aggiorna periodicamente un'entità `WORKER_HEARTBEAT` sulla Table Storage per testimoniare la sua vitalità
- **Stateless Worker**: il filesystem locale viene azzerato (shutil.rmtree) dopo ogni task

## Struttura del Repository

```
ProgettoSDCC/
├── webapp/
│   └── app.py                  # Applicazione Streamlit (frontend + dashboard)
├── worker/
│   ├── worker.py               # Worker AI (polling coda, DeepFace, persistenza)
│   ├── Dockerfile              # Immagine Docker del worker
│   └── requirements-worker.txt # Dipendenze Python del worker
├── utility/
│   └── storage_manager.py      # Helper condivisi per Blob/Table/Queue
├── .github/workflows/
│   ├── webapp-deploy.yml       # CI/CD pipeline per Azure App Service
│   └── worker-deploy.yml       # CI/CD pipeline per Azure Container Instances
└── requirements.txt            # Dipendenze della Web App
```

## Deployment (CI/CD)

Il sistema utilizza **GitHub Actions** per il deployment automatico:

- Ogni push su `master` che modifica `webapp/**` → aggiorna automaticamente l'**Azure App Service**
- Ogni push su `master` che modifica `worker/**` → ricostruisce l'immagine Docker e aggiorna l'**Azure Container Instance**

### Segreti GitHub richiesti

| Secret | Descrizione |
|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | Connection string dello Storage Account Azure |
| `AZURE_CREDENTIALS` | JSON delle credenziali del Service Principal Azure |
| `AZURE_RESOURCE_GROUP` | Nome del Resource Group |
| `REGISTRY_USERNAME` | Username di Azure Container Registry |
| `REGISTRY_PASSWORD` | Password di Azure Container Registry |
| `AZUREAPPSERVICE_PUBLISHPROFILE` | Profilo di pubblicazione di Azure App Service |

## Sviluppo Locale

### Prerequisiti
- Python 3.11+
- [Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite) (emulatore locale Azure Storage)
- Docker (per testare il worker in locale)

### Setup
```bash
# Clona il repository
git clone https://github.com/Rox-ario/ProgettoSDCC_2026.git
cd ProgettoSDCC_2026

# Crea e attiva l'ambiente virtuale
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Installa le dipendenze della webapp
pip install -r requirements.txt

# Crea il file .env con la connection string di Azurite (emulatore locale)
# Avvia Azurite prima di eseguire la webapp:
# azurite --silent --location ./data_emulator

# Avvia la webapp
streamlit run webapp/app.py
```

### Esecuzione del Worker in locale
```bash
pip install -r worker/requirements-worker.txt
python worker/worker.py
```

## Tecnologie Principali
- **Python 3.11**
- **Streamlit** — Web App framework
- **DeepFace 0.0.100** — Libreria AI per il riconoscimento delle emozioni facciali
- **TensorFlow 2.21** — Backend per DeepFace
- **Azure SDK for Python** — azure-storage-blob, azure-storage-queue, azure-data-tables
- **Docker** — Containerizzazione del worker
- **GitHub Actions** — CI/CD
