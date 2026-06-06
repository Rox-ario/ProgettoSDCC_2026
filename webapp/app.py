import os
import sys
import json
import pandas as pd
from azure.data.tables import TableClient
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import HttpResponseError

# Assicuriamoci che la radice del progetto sia nel sys.path *prima* di importare i pacchetti locali
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import streamlit as st
from datetime import datetime
from utility.storage_manager import initialize_azure_resources, send_message_to_queue
from utility.storage_manager import upload_file_to_blob, save_metadata_to_table

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="EmoAnalysis Cloud System",
    page_icon="🎬",
    layout="centered"
)

# Blocco 1: Bootstrap dei servizi cloud (Azurite) all'avvio dell'applicazione
@st.cache_resource
def bootstrap_app():
    """Inizializza le risorse una sola volta all'avvio dell'app"""
    initialize_azure_resources()

bootstrap_app()

# Blocco 2: Interfaccia Grafica - Intestazione
st.title("Sistema di Analisi delle Espressioni Facciali")
st.subheader("Applicazione Cloud-Based per il Rilevamento Multiprofilo delle Emozioni")

st.divider()

# Creazione delle due macro-sezioni (Tabs) dell'applicazione
tab_ingestion, tab_dashboard = st.tabs(["📤 Ingestion Dati", "📊 Dashboard Risultati AI"])

# ==========================================
# TAB 1: INGESTION
# ==========================================
with tab_ingestion:
    st.markdown("""
    Benvenuto nel sistema di ingestion. Carica un'immagine o un breve video contenente uno o più volti 
    e inserisci i metadati richiesti per avviare l'elaborazione distribuita.
    """)

    with st.form("ingestion_form", clear_on_submit=False):
        st.write("### 📝 Metadati del Contenuto Multimediale")

        # Campi di input richiesti dai requisiti del progetto
        subject_id = st.text_input("ID Soggetto / Paziente", placeholder="Es. SUB_0042")

        col1, col2 = st.columns(2)
        with col1:
            acquisition_date = st.date_input("Data di Acquisizione", datetime.today())
        with col2:
            source_type = st.selectbox(
                "Sorgente del Dato",
                ["Upload Manuale", "Dataset Pubblico (Depression Analysis)", "Sorgente Esterna"]
            )

        context_reg = st.text_area("Contesto della Registrazione", placeholder="Es. Intervista clinica, test di laboratorio...")

        st.write("### 📁 File Multimediale")
        uploaded_file = st.file_uploader(
            "Seleziona un'immagine o un breve video (Max 50MB)",
            type=["mp4", "avi", "jpg", "jpeg", "png"]
        )

        submit_button = st.form_submit_button("Invia al Sistema Cloud")

    # Logica di business alla sottomissione del form
    if submit_button:
        if not subject_id or not uploaded_file:
            st.error("⚠️ Attenzione: compilare i campi ID Soggetto e File Multimediale")
        else:
            with st.spinner("Caricamento del file e dei metadati sui sistemi Azure in corso..."):
                try:
                    file_bytes = uploaded_file.getvalue()
                    original_name = uploaded_file.name

                    blob_name, unique_id = upload_file_to_blob(file_bytes, original_name)

                    metadata_payload = {
                        "OriginalFileName": original_name,
                        "BlobName": blob_name,
                        "AcquisitionDate": str(acquisition_date),
                        "SourceType": source_type,
                        "Context": context_reg,
                        "FileSize": uploaded_file.size,
                        "MimeType": uploaded_file.type,
                        "Processed": False,
                        "AnalysisResults": "{}"
                    }

                    save_metadata_to_table(subject_id, unique_id, metadata_payload)
                    send_message_to_queue(unique_id, blob_name, subject_id)

                    st.success("✅ Operazione completata con successo!")
                    st.info(f"**ID Univoco Assegnato (RowKey):** {unique_id}")
                    st.write(f"Il file è stato storicizzato nel Blob come `{blob_name}` e i metadati sono indicizzati NoSQL.")

                except Exception as e:
                    st.error(f"❌ Si è verificato un errore durante il salvataggio in Cloud: {e}")

# ==========================================
# TAB 2: DASHBOARD E VISUALIZZAZIONE
# ==========================================
with tab_dashboard:
    st.write("### 🔍 Ricerca Analisi Completate")
    st.write("Inserisci l'ID del soggetto per visualizzare i risultati inferiti dal Worker asincrono.")

    search_subject_id = st.text_input("ID Soggetto da ricercare:", placeholder="Es. SUB_0042", key="search_sub")

    if search_subject_id:
        try:
            AZURITE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            TABLE_NAME = "MediaMetadata"

            table_client = TableClient.from_connection_string(conn_str=AZURITE_CONNECTION_STRING, table_name=TABLE_NAME)

            # Query OData: Cerchiamo per PartitionKey e controlliamo che Processed sia vero
            query_filter = f"PartitionKey eq '{search_subject_id}' and Processed eq true"

            # Eseguiamo la query e convertiamo il generatore in una lista
            risultati = list(table_client.query_entities(query_filter=query_filter))

            if not risultati:
                st.warning(f"Nessuna analisi completata trovata per il soggetto '{search_subject_id}'. Se hai appena caricato un file, attendi che il worker termini il processo.")
            else:
                st.success(f"Trovati {len(risultati)} task completati per questo soggetto.")

                # Creiamo un dizionario per far scegliere all'utente quale video/task analizzare
                opzioni_task = {
                    ent['RowKey']: f"Video: {ent.get('OriginalFileName', 'Sconosciuto')} (Task: {ent['RowKey']})"
                    for ent in risultati
                }

                selected_task_id = st.selectbox(
                    "Seleziona l'analisi da visualizzare:",
                    options=list(opzioni_task.keys()),
                    format_func=lambda x: opzioni_task[x]
                )

                if selected_task_id:
                    # Estraiamo l'entità scelta
                    entita_selezionata = next(e for e in risultati if e['RowKey'] == selected_task_id)

                    # --- ANTEPRIMA DEL FILE ORIGINALE ---
                    blob_name = entita_selezionata.get('BlobName', '')
                    mime_type = entita_selezionata.get('MimeType', '')
                    original_name = entita_selezionata.get('OriginalFileName', 'File')

                    if blob_name:
                        try:
                            blob_service = BlobServiceClient.from_connection_string(AZURITE_CONNECTION_STRING)
                            blob_client = blob_service.get_blob_client(
                                container=os.getenv("BLOB_CONTAINER_NAME", "multimedia-contents"),
                                blob=blob_name
                            )
                            file_bytes = blob_client.download_blob().readall()

                            st.write("### 🖼️ Anteprima del Contenuto Originale")
                            if mime_type.startswith('image/'):
                                st.image(file_bytes, caption=original_name, use_column_width=True)
                            elif mime_type.startswith('video/'):
                                st.video(file_bytes)
                                st.caption(original_name)
                            else:
                                st.info(f"Tipo di file `{mime_type}` non supportato per l'anteprima.")

                        except Exception as preview_err:
                            st.warning(f"⚠️ Impossibile caricare l'anteprima dal Blob Storage: {preview_err}")

                    st.divider()

                    # Decodifichiamo il JSON salvato dal worker
                    risultati_raw = entita_selezionata.get('AnalysisResults', '[]')
                    dati_emozioni = json.loads(risultati_raw)

                    if dati_emozioni and isinstance(dati_emozioni, list):
                        st.write("### 📈 Andamento Emotivo Apparente")

                        # --- INIZIO LOGICA DI FLATTENING ---
                        # Dobbiamo appiattire il JSON perché Streamlit non può plottare dizionari annidati
                        dati_piatti = []
                        for record in dati_emozioni:
                            riga_piatta = {}

                            for chiave, valore in record.items():
                                if isinstance(valore, dict):
                                    # Se troviamo un dizionario annidato (es. le emozioni di DeepFace)
                                    # estraiamo le chiavi e le mettiamo al primo livello
                                    for sub_chiave, sub_valore in valore.items():
                                        # Prendiamo solo i numeri per il grafico (ignoriamo stringhe come "dominant_emotion")
                                        if isinstance(sub_valore, (int, float)):
                                            riga_piatta[sub_chiave] = sub_valore
                                elif isinstance(valore, (int, float)):
                                    # Se è già un numero (es. il numero del "frame"), lo teniamo
                                    riga_piatta[chiave] = valore

                            # Aggiungiamo solo se abbiamo trovato dei dati utili
                            if riga_piatta:
                                dati_piatti.append(riga_piatta)
                        # --- FINE LOGICA DI FLATTENING ---

                        if dati_piatti:
                            # Creazione del DataFrame Pandas sui dati puliti
                            df = pd.DataFrame(dati_piatti)

                            # Se il worker ha salvato il 'frame', lo usiamo come asse X
                            if 'frame' in df.columns:
                                df.set_index('frame', inplace=True)

                            # Ora Streamlit avrà solo colonne numeriche e disegnerà le linee correttamente!
                            if len(df) == 1:
                                st.info("📸 Rilevato un singolo frame temporale. Visualizzazione tramite grafico a barre.")
                                # Trasponiamo il dataframe per far sì che le emozioni diventino l'asse X del bar chart
                                st.bar_chart(df.T)
                            else:
                                st.info("🎥 Rilevati più frame temporali. Visualizzazione dell'andamento tramite grafico a linee.")
                                st.line_chart(df)

                            # Espansore per il debug
                            with st.expander("Mostra i dati tabellari analizzati"):
                                st.dataframe(df)
                        else:
                            st.info("Impossibile estrarre dati numerici dal JSON per generare il grafico.")
                    else:
                        st.info("Nessun dato temporale o volto rilevato nel JSON per questo task.")

        except HttpResponseError as e:
            st.error(f"Errore di comunicazione con Azure Table Storage (Azurite avviato?). Dettagli: {e}")
        except json.JSONDecodeError:
            st.error("Errore: Il campo AnalysisResults non contiene un JSON valido.")


# Footer accademico obbligatorio
st.sidebar.markdown("---")
st.sidebar.markdown("**Studente:** Rosario Chiappetta")
st.sidebar.markdown("**Corso:** Sistemi Distribuiti e Cloud Computing")
st.sidebar.markdown("**A.A.:** 2025/2026")