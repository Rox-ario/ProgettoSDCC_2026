import os
import sys
# Assicuriamoci che la radice del progetto sia nel sys.path *prima* di importare i pacchetti locali
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import streamlit as st
from datetime import datetime
from utility.storage_manager import initialize_azure_resources

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
    submit_button = st.form_submit_index = st.form_submit_button("Invia al Sistema Cloud")

# Logica temporanea alla pressione del bottone (Placeholder per il prossimo step)
if submit_button:
    if not subject_id or not uploaded_file:
        st.error("❌ Errore: L'ID Soggetto e il File Multimediale sono campi obbligatori!")
    else:
        st.success(f"📌 Form sottomesso correttamente per il soggetto: {subject_id}!")
        st.info("Nel prossimo step collegheremo questo bottone al caricamento reale su Azurite.")

        # Dimostrazione di lettura metadati del file
        file_details = {
            "Nome File": uploaded_file.name,
            "Tipo MIME": uploaded_file.type,
            "Dimensione (Bytes)": uploaded_file.size
        }
        st.json(file_details)

# Footer accademico obbligatorio
st.sidebar.markdown("---")
st.sidebar.markdown("**Studente:** Rosario Chiappetta")
st.sidebar.markdown("**Corso:** Sistemi Distribuiti e Cloud Computing")
st.sidebar.markdown("**A.A.:** 2025/2026")