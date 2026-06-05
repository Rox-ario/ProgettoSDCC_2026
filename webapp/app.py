import os
import sys
# Assicuriamoci che la radice del progetto sia nel sys.path *prima* di importare i pacchetti locali
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import streamlit as st
from datetime import datetime
from utility.storage_manager import initialize_azure_resources, send_message_to_queue

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
st.markdown("""
Benvenuto nel sistema di ingestion. Carica un'immagine o un breve video contenente uno o più volti 
e inserisci i metadati richiesti per avviare l'elaborazione distribuita.
""")

st.divider()

# Blocco 3: Form di inserimento dati e caricamento file
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

    # Pulsante di sottomissione del form
    submit_button = st.form_submit_button("Invia al Sistema Cloud")

# Logica di business alla sottomissione del form
if submit_button:
    if not subject_id or not uploaded_file:
        st.error("⚠️ Attenzione: compilare i campi ID Soggetto e File Multimediale")
    else:
        with st.spinner("Caricamento del file e dei metadati sui sistemi Azure in corso..."):
            try:
                # 1. Leggiamo i byte del file direttamente dalla memoria di Streamlit
                file_bytes = uploaded_file.getvalue()
                original_name = uploaded_file.name

                # 2. Invochiamo il caricamento sul Blob Storage
                # Importiamo le funzioni localmente o in cima al file
                from utility.storage_manager import upload_file_to_blob, save_metadata_to_table

                blob_name, unique_id = upload_file_to_blob(file_bytes, original_name)

                # 3. Prepariamo il dizionario dei metadati da salvare in Table Storage
                metadata_payload = {
                    "OriginalFileName": original_name,
                    "BlobName": blob_name,
                    "AcquisitionDate": str(acquisition_date), # Convertiamo la data in stringa ISO
                    "SourceType": source_type,
                    "Context": context_reg,
                    "FileSize": uploaded_file.size,
                    "MimeType": uploaded_file.type,
                    "Processed": False,                       # Flag utile per il Worker asincrono
                    "AnalysisResults": "{}"                    # Campo JSON vuoto per i risultati multiprofilo futuri
                }

                # 4. Salviamo i metadati nella Tabella NoSQL
                save_metadata_to_table(subject_id, unique_id, metadata_payload)

                send_message_to_queue(unique_id, blob_name, subject_id)

                # Successo!
                st.success("✅ Operazione completata con successo!")
                st.info(f"**ID Univoco Assegnato:** {unique_id}")
                st.write(f"Il file è stato storicizzato nel Blob come `{blob_name}` e i metadati sono indicizzati NoSQL.")

            except Exception as e:
                st.error(f"❌ Si è verificato un errore durante il salvataggio in Cloud: {e}")

# Footer accademico obbligatorio
st.sidebar.markdown("---")
st.sidebar.markdown("**Studente:** Rosario Chiappetta")
st.sidebar.markdown("**Corso:** Sistemi Distribuiti e Cloud Computing")
st.sidebar.markdown("**A.A.:** 2025/2026")