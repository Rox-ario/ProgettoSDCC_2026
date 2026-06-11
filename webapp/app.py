import json
import os
import sys
from typing import Any

import pandas as pd
import plotly.graph_objects as go

# Assicuriamo che la radice del progetto sia importabile
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import streamlit as st
from datetime import datetime
from azure.data.tables import TableClient
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import HttpResponseError

from utility.storage_manager import (
    initialize_azure_resources,
    send_message_to_queue,
    upload_file_to_blob,
    save_metadata_to_table,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COSTANTI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PLATFORM_NAME = "EmoAnalysis"
PLATFORM_SUBTITLE = "Sistema Cloud di Riconoscimento delle Emozioni Facciali"
VERSION = "1.0.0"

AZURITE_CONN = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
TABLE_NAME = os.getenv("TABLE_NAME", "MediaMetadata")
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER_NAME", "multimedia-contents")

# Configurazione visualizzazione emozioni — ordine e colori per grafici coerenti
EMOTION_CONFIG: dict[str, dict[str, str]] = {
    "happy":    {"label": "Felicità", "color": "#4ade80"},
    "sad":      {"label": "Tristezza", "color": "#60a5fa"},
    "angry":    {"label": "Rabbia",    "color": "#f87171"},
    "surprise": {"label": "Sorpresa",  "color": "#fbbf24"},
    "fear":     {"label": "Paura",     "color": "#a78bfa"},
    "disgust":  {"label": "Disgusto",  "color": "#34d399"},
    "neutral":  {"label": "Neutrale",  "color": "#94a3b8"},
}

PLOTLY_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color="#0f172a"),
    margin=dict(l=24, r=24, t=40, b=24),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=11),
    ),
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CSS PERSONALIZZATO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def inject_custom_css():
    """Inietta gli override CSS per il tema scientifico."""
    st.markdown("""
    <style>
    /* ── Google Font ─────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Variabili root ──────────────────────────────── */
    :root {
        --surface:        #ffffff;
        --surface-alt:    #f8fafc;
        --surface-hover:  #f1f5f9;
        --border:         #e2e8f0;
        --border-subtle:  #f1f5f9;
        --text-primary:   #0f172a;
        --text-secondary: #475569;
        --text-muted:     #94a3b8;
        --accent:         #2563eb;
        --accent-light:   #dbeafe;
        --accent-dark:    #1e40af;
        --success:        #059669;
        --success-light:  #d1fae5;
        --warning:        #d97706;
        --warning-light:  #fef3c7;
        --danger:         #dc2626;
        --danger-light:   #fee2e2;
        --radius-sm:      6px;
        --radius-md:      10px;
        --radius-lg:      14px;
        --shadow-sm:      0 1px 2px rgba(0,0,0,.04);
        --shadow-md:      0 2px 8px rgba(0,0,0,.06);
        --shadow-lg:      0 4px 16px rgba(0,0,0,.08);
    }

    /* ── Tipografia globale ───────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }

    /* ── Container principale ────────────────────────── */
    .stApp {
        background-color: var(--surface-alt);
    }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1100px !important;
    }

    /* ── Sidebar ─────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }

    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] .stMarkdown span,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown h4 {
        color: #e2e8f0 !important;
    }

    section[data-testid="stSidebar"] .stMarkdown a {
        color: #93c5fd !important;
    }

    section[data-testid="stSidebar"] hr {
        border-color: #1e293b !important;
    }

    section[data-testid="stSidebar"] .stRadio label span {
        color: #cbd5e1 !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
    }

    section[data-testid="stSidebar"] .stRadio label[data-checked="true"] span {
        color: #ffffff !important;
    }

    /* ── Intestazioni ────────────────────────────────── */
    h1 { font-weight: 700 !important; color: var(--text-primary) !important; letter-spacing: -0.02em !important; font-size: 1.75rem !important; }
    h2 { font-weight: 600 !important; color: var(--text-primary) !important; letter-spacing: -0.01em !important; font-size: 1.35rem !important; }
    h3 { font-weight: 600 !important; color: var(--text-primary) !important; font-size: 1.1rem !important; }

    /* ── Card ─────────────────────────────────────────── */
    .sci-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.2s ease;
    }
    .sci-card:hover { box-shadow: var(--shadow-md); }

    .sci-card-header {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-muted);
        margin-bottom: 0.5rem;
    }

    .sci-card-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.2;
    }

    .sci-card-delta {
        font-size: 0.8rem;
        font-weight: 500;
        margin-top: 0.25rem;
    }

    .delta-positive { color: var(--success); }
    .delta-neutral  { color: var(--text-muted); }
    .delta-warning  { color: var(--warning); }

    /* ── Badge di stato ──────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 100px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .badge-success  { background: var(--success-light); color: var(--success); }
    .badge-warning  { background: var(--warning-light); color: var(--warning); }
    .badge-danger   { background: var(--danger-light);  color: var(--danger); }
    .badge-info     { background: var(--accent-light);  color: var(--accent); }

    /* ── Card metodologia ────────────────────────────── */
    .method-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-left: 3px solid var(--accent);
        border-radius: var(--radius-sm);
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.85rem;
    }
    .method-card h4 {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
        margin-bottom: 0.35rem !important;
    }
    .method-card p {
        font-size: 0.85rem;
        color: var(--text-secondary);
        line-height: 1.6;
        margin: 0;
    }

    /* ── Chip di insight ─────────────────────────────── */
    .insight-chip {
        background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
        border: 1px solid #bae6fd;
        border-radius: var(--radius-sm);
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    .insight-chip-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--accent);
        margin-bottom: 0.3rem;
    }
    .insight-chip-text {
        font-size: 0.88rem;
        color: var(--text-primary);
        line-height: 1.55;
    }

    /* ── Separatore di sezione ───────────────────────── */
    .section-divider {
        border: none;
        border-top: 1px solid var(--border-subtle);
        margin: 2rem 0 1.5rem 0;
    }

    /* ── Stato vuoto ─────────────────────────────────── */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        color: var(--text-muted);
    }
    .empty-state-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
    .empty-state-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-secondary);
        margin-bottom: 0.35rem;
    }
    .empty-state-body { font-size: 0.85rem; line-height: 1.5; }

    /* ── Raffinamenti form ────────────────────────────── */
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox > div > div {
        border-radius: var(--radius-sm) !important;
        border-color: var(--border) !important;
        font-size: 0.9rem !important;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px var(--accent-light) !important;
    }

    /* ── Tab ──────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem;
        border-bottom: 2px solid var(--border-subtle);
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 500 !important;
        font-size: 0.88rem !important;
        color: var(--text-secondary) !important;
        padding: 0.5rem 1rem !important;
        border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent) !important;
    }

    /* ── Pulsante ─────────────────────────────────────── */
    .stFormSubmitButton button {
        background: var(--accent) !important;
        color: #fff !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 1.5rem !important;
        letter-spacing: 0.01em;
        transition: background 0.15s ease, box-shadow 0.15s ease;
    }
    .stFormSubmitButton button:hover {
        background: var(--accent-dark) !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
    }

    /* ── Expander ────────────────────────────────────── */
    .streamlit-expanderHeader {
        font-weight: 500 !important;
        font-size: 0.88rem !important;
        color: var(--text-secondary) !important;
    }

    /* ── Override st.info / st.warning — testo leggibile ─ */
    .stAlert [data-testid="stMarkdownContainer"] p,
    .stAlert [data-testid="stMarkdownContainer"] span,
    .stAlert p,
    .stAlert span,
    div[data-baseweb="notification"] div {
        color: #0f172a !important;
    }

    /* Warning personalizzato per anteprima */
    .preview-warning {
        background: #d97706;
        color: #ffffff !important;
        padding: 0.75rem 1.25rem;
        border-radius: var(--radius-sm);
        font-size: 0.88rem;
        font-weight: 500;
        margin: 0.5rem 0;
    }

    /* ── Footer ──────────────────────────────────────── */
    .sci-footer {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
        font-size: 0.75rem;
        color: var(--text-muted);
        border-top: 1px solid var(--border-subtle);
        margin-top: 3rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMPONENTI HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def metric_card(label: str, value: str, delta: str = "", delta_class: str = "delta-neutral") -> str:
    delta_html = f'<div class="sci-card-delta {delta_class}">{delta}</div>' if delta else ""
    return f"""
    <div class="sci-card">
        <div class="sci-card-header">{label}</div>
        <div class="sci-card-value">{value}</div>
        {delta_html}
    </div>
    """

def empty_state(icon: str, title: str, body: str) -> str:
    return f"""
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <div class="empty-state-title">{title}</div>
        <div class="empty-state-body">{body}</div>
    </div>
    """

def method_card(title: str, body: str) -> str:
    return f"""
    <div class="method-card">
        <h4>{title}</h4>
        <p>{body}</p>
    </div>
    """

def insight_chip(label: str, text: str) -> str:
    return f"""
    <div class="insight-chip">
        <div class="insight-chip-label">{label}</div>
        <div class="insight-chip-text">{text}</div>
    </div>
    """

def badge(text: str, variant: str = "info") -> str:
    return f'<span class="badge badge-{variant}">{text}</span>'

def section_divider():
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER DATI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def flatten_emotion_records(raw_records: list[dict]) -> pd.DataFrame:
    """Appiattisce il JSON e forza tipizzazioni numeriche sicure per Plotly."""
    rows = []
    expected_emotions = ["happy", "sad", "angry", "surprise", "fear", "disgust", "neutral"]

    for record in raw_records:
        row: dict[str, Any] = {}

        # 1. Estrazione campi base
        for key in ("timestamp_second", "face_id", "dominant_emotion", "confidence"):
            if key in record:
                row[key] = record[key]

        # 2. Estrazione emozioni (supporta sia dati annidati in 'metrics' sia piatti)
        metrics = record.get("metrics", record)
        for emotion_key in expected_emotions:
            if emotion_key in metrics:
                row[emotion_key] = metrics[emotion_key]

        if row:
            rows.append(row)

    df = pd.DataFrame(rows)

    # FORZATURA TIPI NUMERICI (Previene crash silenziosi di Plotly)
    if not df.empty:
        if "timestamp_second" in df.columns:
            df["timestamp_second"] = pd.to_numeric(df["timestamp_second"], errors="coerce").fillna(0)

        for col in expected_emotions:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def build_emotion_timeseries(df: pd.DataFrame, selected_emotions: list[str] | None = None) -> go.Figure:
    """Costruisce un grafico multi-linea con legenda sotto e quadrati colorati."""
    emotion_cols = [c for c in df.columns if c in EMOTION_CONFIG]
    if not emotion_cols:
        return None

    # Filtra per le emozioni selezionate dall'utente (se non specificate, mostra tutte)
    if selected_emotions:
        emotion_cols = [c for c in emotion_cols if c in selected_emotions]
    if not emotion_cols:
        return None

    df_clean = df.copy()

    if "timestamp_second" in df_clean.columns:
        df_clean["timestamp_second"] = pd.to_numeric(df_clean["timestamp_second"], errors="coerce")
        df_clean = df_clean.groupby("timestamp_second")[emotion_cols].mean().reset_index()
        df_clean = df_clean.sort_values("timestamp_second")
        x_data = df_clean["timestamp_second"].tolist()
    else:
        df_clean = df_clean.reset_index(drop=True)
        x_data = list(range(len(df_clean)))

    fig = go.Figure()
    for col in emotion_cols:
        cfg = EMOTION_CONFIG[col]
        y_data = pd.to_numeric(df_clean[col], errors="coerce").fillna(0.0).tolist()

        fig.add_trace(go.Scatter(
            x=x_data,
            y=y_data,
            name=cfg["label"],
            line=dict(color=cfg["color"], width=2.5),
            mode="lines+markers",
            marker=dict(size=5, symbol="square"),   # ← marker quadrato per coerenza visiva con la legenda
            hovertemplate=f"<b>{cfg['label']}</b><br>"
                          "Tempo: %{x}s<br>"
                          "Punteggio: %{y:.1f}%<extra></extra>",
        ))

    layout = dict(PLOTLY_LAYOUT_DEFAULTS)
    layout.update(dict(
        dragmode="zoom",
        xaxis=dict(
            title=dict(text="Tempo (secondi)", font=dict(color="#0f172a")),
            showgrid=True, gridcolor="#f1f5f9",
            zeroline=False, tickfont=dict(color="#0f172a"),
        ),
        yaxis=dict(
            title=dict(text="Punteggio Emozione (%)", font=dict(color="#0f172a")),
            showgrid=True, gridcolor="#f1f5f9",
            zeroline=False, range=[-2, 105],
            tickfont=dict(color="#0f172a"),
        ),
        height=400,
        # ── Legenda sotto il grafico ──────────────────────────
        legend=dict(
            orientation="h",        # orizzontale
            yanchor="top",
            y=-0.22,                # negativo = sotto l'area del grafico
            xanchor="center",
            x=0.5,
            font=dict(size=12, color="#0f172a"),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            # I quadrati si ottengono con traceorder e itemsizing
            itemsizing="constant",  # stessa dimensione per tutti i simboli
        ),
        # Sovrascriviamo l'impostazione della legenda ereditata da PLOTLY_LAYOUT_DEFAULTS
    ))
    fig.update_layout(**layout)

    # Forza il simbolo della legenda a quadrato per ogni traccia
    fig.update_traces(legendrank=1)

    return fig


def build_emotion_distribution(df: pd.DataFrame) -> go.Figure:
    """Costruisce un grafico a barre orizzontali dei punteggi medi."""
    emotion_cols = [c for c in df.columns if c in EMOTION_CONFIG]
    if not emotion_cols:
        return None

    means = df[emotion_cols].mean().sort_values(ascending=True)

    colors = [EMOTION_CONFIG[e]["color"] for e in means.index]
    labels = [EMOTION_CONFIG[e]["label"] for e in means.index]

    fig = go.Figure(go.Bar(
        x=means.values,
        y=labels,
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(width=0),
            # Rimosso cornerradius per compatibilità
        ),
        hovertemplate="<b>%{y}</b>: %{x:.1f}%<extra></extra>",
    ))

    # In build_emotion_distribution
    layout = dict(PLOTLY_LAYOUT_DEFAULTS)
    layout.update(dict(
        xaxis=dict(
            title=dict(text="Punteggio Medio (%)", font=dict(color="#0f172a")),
            showgrid=True,
            gridcolor="#f1f5f9",
            zeroline=False,
            tickfont=dict(color="#0f172a"),
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(color="#0f172a"),
        ),
        height=320,
    ))
    fig.update_layout(**layout)
    fig.update_layout(**layout)
    return fig


def build_emotion_radar(df: pd.DataFrame) -> go.Figure:
    """Costruisce un grafico radar delle intensità emotive medie."""
    emotion_cols = [c for c in df.columns if c in EMOTION_CONFIG]
    if not emotion_cols:
        return None

    means = df[emotion_cols].mean()
    labels = [EMOTION_CONFIG[e]["label"] for e in means.index]
    values = means.values.tolist()
    # Chiudiamo il poligono
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]

    fig = go.Figure(go.Scatterpolar(
        r=values_closed,
        theta=labels_closed,
        fill="toself",
        fillcolor="rgba(37,99,235,0.08)",
        line=dict(color="#2563eb", width=2),
        marker=dict(size=6, color="#2563eb"),
        hovertemplate="<b>%{theta}</b>: %{r:.1f}%<extra></extra>",
    ))

    layout = dict(PLOTLY_LAYOUT_DEFAULTS)
    layout.update(dict(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, max(values) * 1.15 if values else 100],
                gridcolor="#e2e8f0",
                linecolor="#e2e8f0",
                tickfont=dict(color="#0f172a"),
            ),
            angularaxis=dict(
                gridcolor="#e2e8f0",
                linecolor="#e2e8f0",
                tickfont=dict(color="#0f172a"),
            ),
        ),
        height=380,
    ))
    fig.update_layout(**layout)
    return fig


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BOOTSTRAP AZURE (caricamento lazy, alla prima interazione)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@st.cache_resource
def bootstrap_azure():
    """Inizializza le risorse Azure (Azurite) esattamente una volta."""
    try:
        initialize_azure_resources()
        return True
    except Exception as e:
        print(f"[ATTENZIONE] Bootstrap Azure fallito: {e}")
        return False

# Inizializzazione al primo utilizzo (attivata dall'interazione utente)
_azure_initialized = False

def ensure_azure_ready():
    """Assicura che Azure sia inizializzato prima delle operazioni che lo richiedono."""
    global _azure_initialized
    if not _azure_initialized:
        _azure_initialized = bootstrap_azure()
    return _azure_initialized


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURAZIONE PAGINA E TEMA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.set_page_config(
    page_title=f"{PLATFORM_NAME} — Piattaforma di Analisi Emotiva",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_custom_css()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with st.sidebar:
    # Identità della piattaforma
    st.markdown(f"""
    <div style="padding: 0.5rem 0 1.25rem 0;">
        <div style="font-size: 1.5rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.03em;">
            🧠 {PLATFORM_NAME}
        </div>
        <div style="font-size: 0.78rem; color: #64748b; margin-top: 0.2rem; line-height: 1.4;">
            {PLATFORM_SUBTITLE}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Navigazione
    st.markdown("""
    <div style="font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
                letter-spacing: 0.1em; color: #64748b; margin-bottom: 0.5rem;">
        Navigazione
    </div>
    """, unsafe_allow_html=True)

    nav = st.radio(
        "Navigazione",
        [
            "📊  Dashboard",
            "📤  Ingestion Dati",
            "🔬  Risultati Analisi",
            "📖  Metodologia",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Stato del sistema
    st.markdown("""
    <div style="font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
                letter-spacing: 0.1em; color: #64748b; margin-bottom: 0.75rem;">
        Stato del Sistema
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
        <div style="width: 7px; height: 7px; border-radius: 50%; background: #4ade80;
                    box-shadow: 0 0 6px rgba(74,222,128,0.5);"></div>
        <span style="font-size: 0.8rem; color: #94a3b8;">Servizi Azure</span>
    </div>
    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
        <div style="width: 7px; height: 7px; border-radius: 50%; background: #4ade80;
                    box-shadow: 0 0 6px rgba(74,222,128,0.5);"></div>
        <span style="font-size: 0.8rem; color: #94a3b8;">Worker IA</span>
    </div>
    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
        <div style="width: 7px; height: 7px; border-radius: 50%; background: #4ade80;
                    box-shadow: 0 0 6px rgba(74,222,128,0.5);"></div>
        <span style="font-size: 0.8rem; color: #94a3b8;">Motore di Storage</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Footer accademico
    st.markdown(f"""
    <div style="padding-top: 0.25rem;">
        <div style="font-size: 0.72rem; color: #64748b; line-height: 1.7;">
            <strong style="color: #94a3b8;">Studente</strong><br>Rosario Chiappetta<br><br>
            <strong style="color: #94a3b8;">Corso</strong><br>Sistemi Distribuiti e Cloud Computing<br><br>
            <strong style="color: #94a3b8;">Anno Accademico</strong><br>2025 / 2026
        </div>
        <div style="font-size: 0.65rem; color: #475569; margin-top: 1rem;">
            v{VERSION}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGINA: DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_dashboard():
    st.markdown("## Panoramica della Piattaforma")
    st.markdown(
        '<p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: -0.5rem;">'
        'Metriche in tempo reale e stato di salute del sistema EmoAnalysis.</p>',
        unsafe_allow_html=True,
    )

    # Tentativo di caricare metriche live da Azure Table
    total_tasks = 0
    completed_tasks = 0
    pending_tasks = 0
    unique_subjects = set()
    recent_analyses = []

    # Assicuriamo che Azure sia inizializzato prima di accedere allo storage
    ensure_azure_ready()

    try:
        table_client = TableClient.from_connection_string(
            conn_str=AZURITE_CONN, table_name=TABLE_NAME
        )
        all_entities = list(table_client.list_entities())
        total_tasks = len(all_entities)

        for ent in all_entities:
            unique_subjects.add(ent.get("PartitionKey", ""))
            if ent.get("Processed"):
                completed_tasks += 1
                recent_analyses.append(ent)
            else:
                pending_tasks += 1

    except Exception:
        pass  # degradazione controllata — mostra stato zero

    num_subjects = len(unique_subjects)
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # Riga KPI
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            metric_card("Invii Totali", str(total_tasks), "Tutti i media caricati"),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card(
                "Analisi Completate",
                str(completed_tasks),
                f"{completion_rate:.0f}% tasso di completamento",
                "delta-positive" if completion_rate > 70 else "delta-warning",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            metric_card(
                "In Coda",
                str(pending_tasks),
                "In attesa di elaborazione" if pending_tasks > 0 else "Coda vuota",
                "delta-warning" if pending_tasks > 0 else "delta-positive",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            metric_card("Soggetti Unici", str(num_subjects), "ID partecipanti distinti"),
            unsafe_allow_html=True,
        )

    section_divider()

    # Analisi recenti + architettura del sistema
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### Analisi Recenti")
        if recent_analyses:
            display_rows = []
            for ent in recent_analyses[-8:]:
                display_rows.append({
                    "Soggetto": ent.get("PartitionKey", "—"),
                    "File": ent.get("OriginalFileName", "—"),
                    "Sorgente": ent.get("SourceType", "—"),
                    "Stato": "✓ Completata",
                })
            st.dataframe(
                pd.DataFrame(display_rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.markdown(
                empty_state(
                    "📭",
                    "Nessuna analisi disponibile",
                    "Carica file multimediali dalla sezione Ingestion Dati per iniziare."
                ),
                unsafe_allow_html=True,
            )

    with col_right:
        st.markdown("### Architettura del Sistema")
        st.markdown(method_card(
            "Pipeline Cloud",
            "Webapp → Azure Blob Storage → Coda → Worker (DeepFace IA) → Table Storage → Dashboard"
        ), unsafe_allow_html=True)
        st.markdown(method_card(
            "Modello di Elaborazione",
            "Consegna asincrona at-least-once con protezione poison-pill e timeout di visibilità."
        ), unsafe_allow_html=True)
        st.markdown(method_card(
            "Schema di Storage",
            "PartitionKey = ID Soggetto · RowKey = UUID · Metriche emotive serializzate come JSON nell'entità Table."
        ), unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGINA: INGESTION DATI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_ingestion():
    st.markdown("## Ingestion Dati")
    st.markdown(
        '<p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: -0.5rem;">'
        'Carica contenuti multimediali per l\'analisi automatica delle emozioni facciali.</p>',
        unsafe_allow_html=True,
    )

    # Banner informativo
    st.markdown("""
    <div class="insight-chip">
        <div class="insight-chip-label">Come funziona</div>
        <div class="insight-chip-text">
            Carica un'immagine o un breve video contenente uno o più volti.
            Il file viene salvato in Azure Blob Storage, i metadati sono indicizzati in Table Storage
            e un messaggio di elaborazione viene inviato al worker IA asincrono tramite Queue Storage.
            DeepFace analizza ogni volto rilevato per sette emozioni di base.
        </div>
    </div>
    """, unsafe_allow_html=True)

    section_divider()

    # Form di ingestion
    with st.form("ingestion_form", clear_on_submit=False):
        st.markdown("### Metadati della Sottomissione")

        col_a, col_b = st.columns(2)
        with col_a:
            subject_id = st.text_input(
                "ID Soggetto / Partecipante",
                placeholder="Es. SUB_0042",
                help="Identificativo univoco del partecipante o soggetto.",
            )
        with col_b:
            source_type = st.selectbox(
                "Sorgente del Dato",
                [
                    "Upload Manuale",
                    "Dataset Pubblico (Depression Analysis)",
                    "Sorgente Esterna",
                ],
            )

        col_c, col_d = st.columns(2)
        with col_c:
            acquisition_date = st.date_input(
                "Data di Acquisizione",
                datetime.today(),
                help="Data in cui il contenuto multimediale è stato originariamente registrato.",
            )
        with col_d:
            st.markdown(
                '<div style="height: 1.7rem;"></div>',
                unsafe_allow_html=True,
            )
            context_reg = st.text_input(
                "Contesto della Registrazione",
                placeholder="Es. Intervista clinica, test di laboratorio…",
            )

        section_divider()

        st.markdown("### File Multimediale")
        uploaded_file = st.file_uploader(
            "Seleziona un'immagine o un breve video (max 50 MB)",
            type=["mp4", "avi", "jpg", "jpeg", "png"],
            help="Formati supportati: MP4, AVI, JPG, JPEG, PNG",
        )

        submit_button = st.form_submit_button("Invia alla Pipeline Cloud")

    # Logica di sottomissione
    if submit_button:
        if not subject_id or not uploaded_file:
            st.error("**Errore di Validazione:** Fornire sia un ID Soggetto che un file multimediale.")
        else:
            with st.spinner("Caricamento del file e registrazione dei metadati in Azure…"):
                ensure_azure_ready()
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
                        "AnalysisResults": "{}",
                    }

                    save_metadata_to_table(subject_id, unique_id, metadata_payload)
                    send_message_to_queue(unique_id, blob_name, subject_id)

                    st.success("**Invio completato con successo.** Il file è stato caricato e messo in coda per l'elaborazione IA.")

                    st.markdown(f"""
                    <div class="sci-card" style="margin-top: 0.5rem;">
                        <div class="sci-card-header">Dettagli della Sottomissione</div>
                        <div style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.8;">
                            <strong>ID Task:</strong> <code>{unique_id}</code><br>
                            <strong>Riferimento Blob:</strong> <code>{blob_name}</code><br>
                            <strong>Soggetto:</strong> {subject_id}<br>
                            <strong>Stato:</strong> {badge("In coda", "warning")}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"**Errore Cloud:** {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGINA: RISULTATI ANALISI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_results():
    st.markdown("## Risultati dell'Analisi")
    st.markdown(
        '<p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: -0.5rem;">'
        'Recupera ed esplora i dati dell\'analisi emotiva per i task completati.</p>',
        unsafe_allow_html=True,
    )

    search_subject = st.text_input(
        "ID Soggetto",
        placeholder="Es. SUB_0042",
        key="search_sub",
        help="Inserisci l'ID Soggetto utilizzato durante l'ingestion dei dati.",
    )

    if not search_subject:
        st.markdown(
            empty_state(
                "🔎",
                "Inserisci un ID Soggetto",
                "Digita un identificativo del partecipante qui sopra per cercare le analisi completate.",
            ),
            unsafe_allow_html=True,
        )
        return

    # Assicuriamo che Azure sia inizializzato prima di interrogare lo storage
    ensure_azure_ready()

    try:
        table_client = TableClient.from_connection_string(
            conn_str=AZURITE_CONN, table_name=TABLE_NAME
        )
        query_filter = f"PartitionKey eq '{search_subject}' and Processed eq true"
        results = list(table_client.query_entities(query_filter=query_filter))
    except HttpResponseError as e:
        st.error(f"**Errore di Storage:** Impossibile connettersi ad Azure Table Storage. Azurite è in esecuzione? — {e}")
        return
    except Exception as e:
        st.error(f"**Errore Imprevisto:** {e}")
        return

    if not results:
        st.markdown(
            empty_state(
                "📭",
                "Nessuna analisi completata per \u201c" + search_subject + "\u201d",
                "Se hai caricato un file di recente, attendi che il worker IA termini l'elaborazione.",
            ),
            unsafe_allow_html=True,
        )
        return

    # Selettore task
    st.markdown(f"""
    <div style="margin: 0.5rem 0 1rem 0;">
        {badge(f"{len(results)} completate", "success")}
    </div>
    """, unsafe_allow_html=True)

    task_options = {
        ent["RowKey"]: f"{ent.get('OriginalFileName', 'Sconosciuto')}  —  {ent['RowKey'][:8]}…"
        for ent in results
    }

    selected_task = st.selectbox(
        "Seleziona analisi",
        options=list(task_options.keys()),
        format_func=lambda x: task_options[x],
    )

    if not selected_task:
        return

    entity = next(e for e in results if e["RowKey"] == selected_task)

    section_divider()

    # Riepilogo metadati
    st.markdown("### Metadati del Task")
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.markdown(metric_card(
            "File", entity.get("OriginalFileName", "—"), entity.get("MimeType", "")
        ), unsafe_allow_html=True)
    with mc2:
        st.markdown(metric_card(
            "Sorgente", entity.get("SourceType", "—"), entity.get("AcquisitionDate", "")
        ), unsafe_allow_html=True)
    with mc3:
        size_bytes = entity.get("FileSize", 0)
        size_display = f"{int(size_bytes) / 1024:.0f} KB" if size_bytes else "—"
        st.markdown(metric_card(
            "Dimensione File", size_display, badge("Elaborato", "success")
        ), unsafe_allow_html=True)

    section_divider()

    # Anteprima media
    blob_name = entity.get("BlobName", "")
    mime_type = entity.get("MimeType", "")
    original_name = entity.get("OriginalFileName", "File")

    if blob_name:
        try:
            blob_service = BlobServiceClient.from_connection_string(AZURITE_CONN)
            blob_client = blob_service.get_blob_client(container=BLOB_CONTAINER, blob=blob_name)
            file_bytes = blob_client.download_blob().readall()

            st.markdown("### Anteprima del Contenuto Originale")
            if mime_type.startswith("image/"):
                st.image(file_bytes, caption=original_name, use_column_width=True)
            elif mime_type.startswith("video/"):
                st.video(file_bytes)
                st.caption(original_name)
            else:
                st.info(f"Anteprima non disponibile per il tipo MIME `{mime_type}`.")
        except Exception:
            st.markdown(
                '<div class="preview-warning">⚠️ Impossibile caricare l\'anteprima attualmente</div>',
                unsafe_allow_html=True,
            )

    section_divider()

    # Grafici analisi emotiva
    raw_json = entity.get("AnalysisResults", "[]")
    try:
        raw_records = json.loads(raw_json)
    except json.JSONDecodeError:
        st.error("**Errore Dati:** Il campo dei risultati dell'analisi contiene un JSON non valido.")
        return

    if not raw_records or not isinstance(raw_records, list):
        st.markdown(
            empty_state(
                "🔍",
                "Nessun dato emotivo rilevato",
                "Il worker IA non ha rilevato volti o emozioni in questo file multimediale.",
            ),
            unsafe_allow_html=True,
        )
        return

    df = flatten_emotion_records(raw_records)

    if df.empty:
        st.markdown(
            empty_state("📉", "Impossibile estrarre dati numerici", "Il JSON dell'analisi non contiene valori rappresentabili graficamente."),
            unsafe_allow_html=True,
        )
        return

    st.markdown("### Analisi delle Emozioni")

    # Riepilogo emozione dominante
    if "dominant_emotion" in df.columns:
        dominant_counts = df["dominant_emotion"].value_counts()
        dominant_most = dominant_counts.index[0] if len(dominant_counts) > 0 else "—"
        unique_emotions = len(dominant_counts)

        # Mappa per tradurre l'emozione dominante
        emotion_translate = {
            "happy": "Felicità", "sad": "Tristezza", "angry": "Rabbia",
            "surprise": "Sorpresa", "fear": "Paura", "disgust": "Disgusto",
            "neutral": "Neutrale",
        }
        dominant_label = emotion_translate.get(dominant_most, dominant_most.capitalize())

        dc1, dc2 = st.columns(2)
        with dc1:
            st.markdown(metric_card(
                "Emozione Dominante",
                dominant_label,
                f"Rilevata in {dominant_counts.iloc[0]}/{len(df)} frame" if len(dominant_counts) > 0 else "",
                "delta-positive",
            ), unsafe_allow_html=True)
        with dc2:
            st.markdown(metric_card(
                "Diversità Emotiva",
                str(unique_emotions),
                "su 7 emozioni di base",
            ), unsafe_allow_html=True)

    tab_timeline, tab_distribution, tab_radar, tab_data = st.tabs([
        "📈 Andamento", "📊 Distribuzione", "🎯 Profilo Radar", "📋 Dati Grezzi"
    ])

    with tab_timeline:
        if len(df) > 1:
            fig_ts = build_emotion_timeseries(df)
            if fig_ts:
                st.caption(
                    "💡 **Suggerimento:** trascina sul grafico per zoomare su un intervallo, "
                    "doppio click per tornare alla vista completa. "
                    "Usa i pulsanti in alto a destra per ulteriori opzioni."
                )
                st.plotly_chart(
                    fig_ts,
                    use_container_width=True,
                    config={
                        "displayModeBar": True,
                        "displaylogo": False,
                        "modeBarButtonsToRemove": ["autoScale2d", "lasso2d"],
                        "scrollZoom": True,
                    },
                )
            else:
                st.info("L'andamento temporale richiede colonne con punteggi emotivi nei dati.")
        else:
            st.info("La visualizzazione temporale richiede più punti nel tempo (analisi video).")
            fig_dist = build_emotion_distribution(df)
            if fig_dist:
                st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})

    with tab_distribution:
        fig_dist = build_emotion_distribution(df)
        if fig_dist:
            st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Il grafico di distribuzione richiede colonne con punteggi emotivi.")

    with tab_radar:
        fig_radar = build_emotion_radar(df)
        if fig_radar:
            st.plotly_chart(fig_radar, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Il grafico radar richiede colonne con punteggi emotivi.")

    with tab_data:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} record · {len(df.columns)} colonne")

    # Insight
    section_divider()
    st.markdown("### Insight Analitici")

    emotion_cols = [c for c in df.columns if c in EMOTION_CONFIG]
    if emotion_cols:
        means = df[emotion_cols].mean()
        max_emotion = means.idxmax()
        min_emotion = means.idxmin()

        col_i1, col_i2 = st.columns(2)
        with col_i1:
            st.markdown(insight_chip(
                "Intensità Media più Alta",
                f"<strong>{EMOTION_CONFIG[max_emotion]['label']}</strong> ha ottenuto "
                f"un punteggio medio del {means[max_emotion]:.1f}% su tutti i volti e i frame rilevati.",
            ), unsafe_allow_html=True)
        with col_i2:
            st.markdown(insight_chip(
                "Intensità Media più Bassa",
                f"<strong>{EMOTION_CONFIG[min_emotion]['label']}</strong> ha ottenuto "
                f"un punteggio medio del {means[min_emotion]:.1f}%, suggerendo una presenza minima.",
            ), unsafe_allow_html=True)

        if len(df) > 1:
            # Insight sulla volatilità
            stds = df[emotion_cols].std()
            most_volatile = stds.idxmax()
            st.markdown(insight_chip(
                "Variabilità Emotiva",
                f"<strong>{EMOTION_CONFIG[most_volatile]['label']}</strong> ha mostrato la variabilità "
                f"più elevata (σ = {stds[most_volatile]:.1f}%), indicando fluttuazioni nel tempo.",
            ), unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGINA: METODOLOGIA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_methodology():
    st.markdown("## Metodologia e Documentazione")
    st.markdown(
        '<p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: -0.5rem;">'
        'Dettagli tecnici sulla pipeline di analisi, il modello IA e l\'architettura del sistema.</p>',
        unsafe_allow_html=True,
    )

    section_divider()

    # Panoramica della pipeline
    st.markdown("### Pipeline di Analisi")

    st.markdown(method_card(
        "1 — Acquisizione dei Media",
        "Il contenuto multimediale (immagini o video) viene caricato tramite l'interfaccia web. "
        "Ai file viene assegnato un UUID univoco che lo possa identificare"
        " e vengono archiviati in Azure Blob Storage. I metadati (ID soggetto, "
        "data di acquisizione, sorgente, contesto) vengono salvati in modo persistente in Azure Table Storage con "
        "PartitionKey = IDSoggetto e RowKey = UUID. Insieme, PartitionKey e RowKey formano la chiave primaria per "
        "identificare univocamente ogni task di analisi (anche in presenza di più file caricati dallo stesso soggetto)"
    ), unsafe_allow_html=True)

    st.markdown(method_card(
        "2 — Dispatch Asincrono",
        "Un messaggio JSON contenente il riferimento al blob, la partition key e la row key viene inviato ad "
        "Azure Queue Storage. Il sistema implementa semantiche di consegna at-least-once con un "
        "timeout di visibilità di 5 minuti e rilevamento poison-pill (>5 tentativi di dequeue)."
    ), unsafe_allow_html=True)

    st.markdown(method_card(
        "3 — Estrazione Frame (Video)",
        "Per i file video, OpenCV estrae frame a intervalli di 1 secondo utilizzando un campionamento "
        "FPS-aware. L'estrazione usa l'ottimizzazione grab/retrieve per saltare i frame non target "
        "senza decodifica completa, minimizzando l'uso di memoria e CPU."
    ), unsafe_allow_html=True)

    st.markdown(method_card(
        "4 — Riconoscimento Emotivo tramite IA",
        "Ogni frame estratto viene analizzato utilizzando DeepFace con il modulo di azione emotion. "
        "Il modello rileva tutti i volti in ogni frame e produce distribuzioni di probabilità "
        "per sette emozioni di base: felicità, tristezza, rabbia, sorpresa, paura, disgusto e neutrale. "
        "La confidenza del rilevamento facciale viene registrata insieme alle metriche emotive."
    ), unsafe_allow_html=True)

    st.markdown(method_card(
        "5 — Persistenza dei Risultati",
        "I risultati dell'analisi vengono serializzati come JSON e uniti all'entità originale in Table Storage "
        "utilizzando UpdateMode.MERGE, preservando i metadati esistenti. Il flag Processed viene "
        "impostato a True, e il messaggio dalla coda viene eliminato solo dopo la persistenza riuscita "
        "(garanzia transazionale)."
    ), unsafe_allow_html=True)

    section_divider()

    # Dettagli del modello emotivo
    st.markdown("### Modello di Classificazione delle Emozioni")

    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.markdown("""
        <div class="sci-card">
            <div class="sci-card-header">Specifiche del Modello</div>
            <div style="font-size: 0.88rem; color: var(--text-secondary); line-height: 2;">
                <strong>Framework:</strong> DeepFace<br>
                <strong>Backend:</strong> TensorFlow / Keras<br>
                <strong>Rilevamento:</strong> Multi-volto, per-frame<br>
                <strong>Output:</strong> 7 probabilità emotive (%)<br>
                <strong>Enforcement:</strong> Soft (nessun crash su mancato rilevamento)
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_m2:
        st.markdown("""
        <div class="sci-card">
            <div class="sci-card-header">Tassonomia delle Emozioni</div>
            <div style="font-size: 0.88rem; color: var(--text-secondary); line-height: 2;">
                Basata sulle sei emozioni di base di Ekman più lo stato neutrale.<br><br>
                Felicità · Tristezza · Rabbia · Sorpresa · Paura · Disgusto · Neutrale
            </div>
        </div>
        """, unsafe_allow_html=True)

    section_divider()

    # Architettura cloud
    st.markdown("### Architettura Cloud")

    st.markdown("""
    <div class="sci-card">
        <div class="sci-card-header">Topologia dei Servizi Azure</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem; color: var(--text-secondary);">
            <thead>
                <tr style="border-bottom: 2px solid var(--border);">
                    <th style="text-align: left; padding: 0.6rem 0.5rem; font-weight: 600; color: var(--text-primary);">Servizio</th>
                    <th style="text-align: left; padding: 0.6rem 0.5rem; font-weight: 600; color: var(--text-primary);">Ruolo</th>
                    <th style="text-align: left; padding: 0.6rem 0.5rem; font-weight: 600; color: var(--text-primary);">Risorsa</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid var(--border-subtle);">
                    <td style="padding: 0.5rem;">Azure Blob Storage</td>
                    <td style="padding: 0.5rem;">Archiviazione media binari</td>
                    <td style="padding: 0.5rem;"><code>multimedia-contents</code></td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-subtle);">
                    <td style="padding: 0.5rem;">Azure Queue Storage</td>
                    <td style="padding: 0.5rem;">Dispatch asincrono dei task</td>
                    <td style="padding: 0.5rem;"><code>video-processing-queue</code></td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-subtle);">
                    <td style="padding: 0.5rem;">Azure Table Storage</td>
                    <td style="padding: 0.5rem;">Metadati + risultati (NoSQL)</td>
                    <td style="padding: 0.5rem;"><code>MediaMetadata</code></td>
                </tr>
                <tr>
                    <td style="padding: 0.5rem;">Azurite</td>
                    <td style="padding: 0.5rem;">Emulatore sviluppo locale</td>
                    <td style="padding: 0.5rem;"><code>127.0.0.1:10000-10002</code></td>
                </tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

    section_divider()

    # Riferimenti bibliografici
    st.markdown("### Riferimenti Bibliografici")
    st.markdown("""
    <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 2;">
        1. Ekman, P. (1992). <em>An argument for basic emotions.</em> Cognition & Emotion, 6(3-4), 169–200.<br>
        2. Serengil, S. I., & Ozpinar, A. (2024). <em>A Benchmark of Facial Recognition Pipelines and Co-Usability Performances of Modules.</em> Journal of Information Technologies, 17(2), 95-107.<br>
        3. Microsoft Azure Documentation — <em>Azure Storage Services REST API Reference.</em><br>
        4. Bradski, G. (2000). <em>The OpenCV Library.</em> Dr. Dobb's Journal of Software Tools.
    </div>
    """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ROUTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if "Dashboard" in nav:
    render_dashboard()
elif "Ingestion" in nav:
    render_ingestion()
elif "Risultati" in nav:
    render_results()
elif "Metodologia" in nav:
    render_methodology()

# ── Footer ──────────────────────────────────────────────────
st.markdown(f"""
<div class="sci-footer">
    {PLATFORM_NAME} v{VERSION} · Sistemi Distribuiti e Cloud Computing · A.A. 2025/2026
</div>
""", unsafe_allow_html=True)
