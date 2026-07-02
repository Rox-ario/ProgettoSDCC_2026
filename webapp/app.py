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
from datetime import datetime, timezone
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

PLATFORM_NAME = "Orfeo"
PLATFORM_SUBTITLE = "Piattaforma Cloud di Affective Computing AI-Based"
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

    section[data-testid="stSidebar"] .stRadio label p {
        color: #cbd5e1 !important;
        font-size: 1.1rem !important;
        font-weight: 500 !important;
    }

    section[data-testid="stSidebar"] .stRadio label[data-checked="true"] p {
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
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
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
    .stSelectbox div[data-baseweb="select"],
    .stDateInput input {
        background-color: var(--surface) !important;
        color: var(--text-primary) !important;
        border-radius: var(--radius-sm) !important;
        border: 1px solid var(--border) !important;
        font-size: 0.9rem !important;
        box-shadow: var(--shadow-sm) !important;
        transition: all 0.2s ease;
    }
    
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox div[data-baseweb="select"]:focus-within,
    .stDateInput input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-light) !important;
        outline: none !important;
    }

    /* Styling dell'area di Drag & Drop del File Uploader */
    [data-testid="stFileUploader"] section {
        background-color: var(--surface) !important;
        border: 2px dashed var(--border) !important;
        border-radius: var(--radius-md) !important;
        padding: 2rem !important;
        transition: all 0.2s ease;
    }
    
    [data-testid="stFileUploader"] section:hover {
        border-color: var(--accent) !important;
        background-color: var(--surface-hover) !important;
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
    .stTextInput label p,
    .stSelectbox label p,
    .stDateInput label p,
    .stFileUploader label p {
        color: #000000 !important;
        font-weight: 600 !important;
    }
    [data-testid="stCaptionContainer"] {
        color: #000000 !important;
    }
    [data-testid="stCaptionContainer"] p {
        color: #000000 !important;
    }
    .stTextArea div[data-testid="InputInstructions"] {
        display: none !important;
    }
    .stTextArea label,
    .stTextArea label p,
    .stTextArea label span,
    div[data-testid="stTextArea"] label p {
        color: #000000 !important;
        font-weight: 600 !important;
    }
    [data-testid="stFileUploader"] > div > div:nth-child(2) *,
    div[data-testid="stUploadedFile"] *,
    .stFileUploaderFileName {
        color: #000000 !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stFileUploader"] > div > div:nth-child(2) button svg,
    div[data-testid="stUploadedFile"] button svg,
    button[title="Remove file"] svg,
    button[aria-label="Remove file"] svg {
        stroke: #000000 !important;
        fill: #000000 !important;
    }
    
    .sci-table-container {
        width: 100%;
        border-radius: var(--radius-md);
        border: 1px solid var(--border);
        overflow: hidden;
        background: var(--surface);
        box-shadow: var(--shadow-sm);
        margin-top: 0.5rem;
    }
    .sci-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.88rem;
        text-align: left;
    }
    .sci-table thead tr {
        background-color: var(--surface-alt);
        border-bottom: 1px solid var(--border);
        color: var(--text-secondary);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.75rem;
    }
    .sci-table th, .sci-table td {
        padding: 0.85rem 1.25rem;
    }
    .sci-table tbody tr {
        border-bottom: 1px solid var(--border-subtle);
        transition: background-color 0.15s ease;
    }
    .sci-table tbody tr:last-child {
        border-bottom: none;
    }
    .sci-table tbody tr:hover {
        background-color: var(--surface-hover);
    }
    .sci-table td {
        color: var(--text-primary);
        font-weight: 500;
    }
    /* ── Nascondere Menu Sviluppatore (Deploy) ───────────────── */
    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* ── Fix Bottone Refresh e Bottoni Secondari ───────────────── */
    button[kind="secondary"] {
        background-color: transparent !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-secondary) !important;
        padding: 0.2rem 0.5rem !important;
        transition: all 0.2s ease;
    }
    button[kind="secondary"]:hover {
        background-color: var(--surface-hover) !important;
        border-color: var(--border) !important;
        color: var(--text-primary) !important;
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
        <div class="sci-card-value" title="{value}">{value}</div>
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
        margin=dict(b=80),  # <--- AGGIUNTA: Aumenta il margine inferiore per fare spazio alla legenda
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
        height=420, # Leggero aumento dell'altezza totale per compensare il margine
        # ── Legenda sotto il grafico ──────────────────────────
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.35,                # <--- MODIFICA QUI: Sposta la legenda più in basso (prima era -0.22)
            xanchor="center",
            x=0.5,
            font=dict(size=12, color="#0f172a"),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            itemsizing="constant",
        ),
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
    page_title=f"{PLATFORM_NAME} — Emotional Pattern Analysis",
    page_icon="🪉",
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
            🪉 {PLATFORM_NAME}
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
            "📊  Data Hub", #TODO chiamalo DataHub
            "📤  Area Input",
            "🔬  Risultati Analisi",
            "📖  Metodologia",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # === HEALTH CHECKS & HEARTBEAT (Stato del Sistema Dinamico) ===

    # 1. Bottone di Soft-Refresh per aggiornare lo stato senza ricaricare la pagina
    col_status_1, col_status_2 = st.columns([4, 1])
    with col_status_1:
        st.markdown("""
        <div style="font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
                    letter-spacing: 0.1em; color: #64748b; margin-bottom: 0.75rem;">
            Stato del Sistema
        </div>
        """, unsafe_allow_html=True)
    with col_status_2:
        # Questo pulsante fa ripartire lo script aggiornando i pallini in tempo reale
        if st.button("🔄", help="Aggiorna stato dei servizi", key="refresh_status"):
            st.rerun()

    try:
        # 2. Check su Azure/Storage
        tc = TableClient.from_connection_string(
            conn_str=AZURITE_CONN,
            table_name=TABLE_NAME,
            retry_total=0,
            connection_timeout=1,
            read_timeout=1
        )
        next(tc.list_entities(), None)
        color_az = "#4ade80" # Verde (Online)
        shadow_az = "0 0 6px rgba(74,222,128,0.5)"

        # 3. Check sul Worker IA tramite Heartbeat Pattern
        try:
            # Andiamo a leggere il battito cardiaco lasciato dal worker
            heartbeat = tc.get_entity(partition_key="SYSTEM", row_key="WORKER_HEARTBEAT")
            last_seen_str = heartbeat.get("LastSeen", "")

            # Parsing sicuro del timestamp ISO
            if last_seen_str.endswith("Z"):
                last_seen_str = last_seen_str.replace("Z", "+00:00")
            last_seen = datetime.fromisoformat(last_seen_str)
            now = datetime.now(timezone.utc)

            # Se il worker ha scritto negli ultimi 15 secondi, è in funzione! (Verde)
            if (now - last_seen).total_seconds() <= 15:
                color_wk = "#4ade80" # Verde
                shadow_wk = "0 0 6px rgba(74,222,128,0.5)"
            else:
                color_wk = "#f87171" # Rosso (Processo morto o bloccato)
                shadow_wk = "0 0 6px rgba(248,113,113,0.5)"
        except Exception:
            # L'entità non esiste ancora: Worker mai avviato (Rosso)
            color_wk = "#f87171"
            shadow_wk = "0 0 6px rgba(248,113,113,0.5)"

    except Exception:
        # Effetto a cascata (Cascade Failure)
        color_az = "#f87171"
        shadow_az = "0 0 6px rgba(248,113,113,0.5)"
        color_wk = "#f87171"
        shadow_wk = "0 0 6px rgba(248,113,113,0.5)"

    # Renderizzazione dinamica HTML
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
        <div style="width: 7px; height: 7px; border-radius: 50%; background: {color_az};
                    box-shadow: {shadow_az};"></div>
        <span style="font-size: 0.8rem; color: #94a3b8;">Servizi Azure</span>
    </div>
    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
        <div style="width: 7px; height: 7px; border-radius: 50%; background: {color_wk};
                    box-shadow: {shadow_wk};"></div>
        <span style="font-size: 0.8rem; color: #94a3b8;">Worker IA</span>
    </div>
    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
        <div style="width: 7px; height: 7px; border-radius: 50%; background: {color_az};
                    box-shadow: {shadow_az};"></div>
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
# PAGINA: DATA HUB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_dashboard():
    st.markdown("## Panoramica della Piattaforma")
    st.markdown(
        '<p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: -0.5rem;">'
        'Metriche in tempo reale e stato di salute del sistema.</p>',
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

        # Resettiamo il total_tasks (lo calcoleremo noi ignorando i record di sistema)
        total_tasks = 0

        for ent in all_entities:
            #Ignoriamo i record di telemetria (Heartbeat) e altri record di sistema che non rappresentano task di analisi reali
            if ent.get("PartitionKey") == "SYSTEM":
                continue

            # Se siamo qui, è un task reale. Aggiorniamo le metriche:
            total_tasks += 1
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
            # Costruzione dinamica di una tabella HTML stilizzata
            table_html = "<div class='sci-table-container'><table class='sci-table'><thead><tr>"
            table_html += "<th>Soggetto</th><th>File</th><th>Sorgente</th><th>Stato</th></tr></thead><tbody>"

            # Iteriamo la lista al contrario per mostrare i task più recenti in cima
            for ent in reversed(recent_analyses[-8:]):
                subject = ent.get("PartitionKey", "—")
                file_name = ent.get("OriginalFileName", "—")
                source = ent.get("SourceType", "—")

                # Applichiamo il troncamento al nome del file direttamente in Python per pulizia visiva
                short_file = file_name if len(file_name) <= 25 else file_name[:22] + "..."

                table_html += f"<tr>"
                table_html += f"<td>{subject}</td>"
                # Aggiungiamo il tooltip nativo (title) per rivelare il nome completo
                table_html += f"<td title='{file_name}' style='color: var(--text-secondary);'>{short_file}</td>"
                table_html += f"<td><span style='color: var(--text-secondary); font-weight: 400;'>{source}</span></td>"
                # Sfruttiamo la nostra funzione helper per iniettare il badge HTML
                table_html += f"<td>{badge('Completata', 'success')}</td>"
                table_html += "</tr>"

            table_html += "</tbody></table></div>"

            st.markdown(table_html, unsafe_allow_html=True)
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
# PAGINA: Area Input
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_ingestion():
    st.markdown("## Centro di acquisizione dati")
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

    acquisition_date = st.date_input(
        "Data di Acquisizione",
        datetime.today(),
        help="Data in cui il contenuto multimediale è stato originariamente registrato.",
    )

    context_reg = st.text_area(
        "Contesto della Registrazione",
        placeholder="Es. Intervista clinica, anamnesi iniziale, test di laboratorio guidato…",
        height=100,
    )

    section_divider()

    st.markdown("### File Multimediale")
    uploaded_file = st.file_uploader(
        "Seleziona un'immagine o un breve video (max 50 MB)",
        type=["mp4", "avi", "jpg", "jpeg", "png"],
        help="Formati supportati: MP4, AVI, JPG, JPEG, PNG. Puoi usare la 'X' accanto al file per rimuoverlo prima dell'invio.",
    )

    st.markdown("<br>", unsafe_allow_html=True) # Un po' di respiro prima dei bottoni

    # Bottoni (Sostituiti st.form_submit_button con normali st.button)
    col_btn1, col_btn2 = st.columns([1, 8])
    with col_btn1:
        submit_button = st.button("Carica file", type="primary")
    with col_btn2:
        cancel_button = st.button("Rimuovi file caricato", type="secondary")

    # Logica di annullamento
    if cancel_button:
        st.rerun()

    # Logica di sottomissione (ora agganciata al bottone normale)
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

    # 1. Ci assicuriamo che Azure sia pronto PRIMA di disegnare l'interfaccia
    ensure_azure_ready()

    # 2. Recuperiamo i soggetti unici per popolare i suggerimenti
    available_subjects = []
    try:
        table_client = TableClient.from_connection_string(
            conn_str=AZURITE_CONN, table_name=TABLE_NAME
        )
        # Ottimizzazione: scarichiamo SOLO la colonna PartitionKey per non appesantire la rete
        entities = table_client.query_entities(
            query_filter="Processed eq true",
            select=["PartitionKey"]
        )
        # Usiamo 'set' per eliminare i duplicati e 'sorted' per ordinarli alfabeticamente
        available_subjects = sorted(list(set(ent["PartitionKey"] for ent in entities)))

    except HttpResponseError as e:
        st.error(f"**Errore di Storage:** Impossibile connettersi ad Azure Table Storage. Azurite è in esecuzione? — {e}")
        return
    except Exception as e:
        st.error(f"**Errore Imprevisto:** {e}")
        return

    # 3. Disegniamo il campo di ricerca con Autocompletamento (Google-style)
    # Sostituito st.text_input con st.selectbox
    search_subject = st.selectbox(
        "ID Soggetto",
        options=available_subjects,
        index=None,  # Il parametro chiave: fa partire il campo vuoto invece di selezionare il primo della lista
        placeholder="Digita per cercare (es. SUB_0042)...",
        key="search_sub",
        help="Digita le prime lettere dell'ID Soggetto per vedere i suggerimenti e selezionare il partecipante.",
    )

    # 4. Gestione dello stato vuoto (se l'utente non ha ancora selezionato nulla)
    if not search_subject:
        st.markdown(
            empty_state(
                "🔎",
                "Ricerca un'immagine o un video analizzata/o",
                "Inserisci l’ID di un’immagine o di un video già caricato per consultare i risultati dell’analisi.",
            ),
            unsafe_allow_html=True,
        )
        return

    # 5. Recupero dei task completi per il soggetto selezionato
    try:
        # Manteniamo la regola di sicurezza (escaping) che abbiamo aggiunto prima!
        safe_search_subject = search_subject.replace("'", "''")

        query_filter = f"PartitionKey eq '{safe_search_subject}' and Processed eq true"
        results = list(table_client.query_entities(query_filter=query_filter))

    except HttpResponseError as e:
        st.error(f"**Errore di Storage:** {e}")
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

    context_text = entity.get("Context", "Nessun contesto o descrizione forniti per questo file.")
    st.markdown(insight_chip("Info", context_text), unsafe_allow_html=True)

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

            if mime_type.startswith("image/"):
                st.image(file_bytes, use_column_width=True)
            elif mime_type.startswith("video/"):
                st.video(file_bytes)
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
                f"{str(unique_emotions)} emozioni rilevate" if unique_emotions > 1 else "1 emozione rilevata" if unique_emotions == 1 else "Nessuna emozione rilevata",
                "su 7 emozioni di base",
            ), unsafe_allow_html=True)

    tab_timeline, tab_distribution, tab_radar, tab_data = st.tabs([
        "📈 Andamento", "📊 Distribuzione", "🕸️ Grafico radar", "📋 Dati Grezzi"
    ])

    with tab_timeline:
        if len(df) > 1:
            fig_ts = build_emotion_timeseries(df)
            if fig_ts:
                st.caption(
                    "**Suggerimenti:** \n- trascina sul grafico per zoomare su un intervallo"
                    "\n- doppio click per tornare alla vista completa."
                    "\n- singolo click su un colore della legenda sotto la dicitura 'Tempo' per eliminare un colore e focalizzarti sugli altri."
                    "\n- doppio click su un colore della legenda per focalizzarti solo su esso."
                    "\n- Usa i pulsanti in alto a destra del grafico per ulteriori opzioni."
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
            st.info("L'andamento temporale richiede l'analisi di più punti nel tempo. Dato che hai caricato un'immagine singola, esplora i risultati nelle tab 'Distribuzione' e 'Grafico Radar'.")

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
        # 1. Arrotondiamo i decimali per una lettura più pulita e leggibile
        df_display = df.copy()
        numeric_cols = [c for c in df_display.columns if c != 'dominant_emotion']
        for c in numeric_cols:
            if c in df_display.columns:
                df_display[c] = pd.to_numeric(df_display[c]).round(3)

        # 2. Costruiamo una tabella interattiva e scrollabile nativa con Plotly
        fig_table = go.Figure(data=[go.Table(
            header=dict(
                values=[f"<b>{c.upper()}</b>" for c in df_display.columns],
                fill_color='#f8fafc', # Colore di sfondo intestazioni (surface-alt)
                align='left',
                font=dict(color='#475569', size=11, family="Inter, sans-serif"),
                line_color='#e2e8f0'  # Colore dei bordi
            ),
            cells=dict(
                values=[df_display[c] for c in df_display.columns],
                fill_color='#ffffff', # Colore di sfondo righe (surface)
                align='left',
                font=dict(color='#0f172a', size=13, family="Inter, sans-serif"),
                line_color='#f1f5f9',
                height=32
            )
        )])

        dynamic_height = min(400, 40 + (len(df_display) * 32))

        # 3. Rimuoviamo i margini per farla aderire perfettamente al container Streamlit
        fig_table.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            height=dynamic_height, # <-- Sostituito il 400 fisso con la variabile dinamica
            paper_bgcolor="rgba(0,0,0,0)"
        )

        # Disegniamo la tabella disabilitando la barra degli strumenti di Plotly
        st.plotly_chart(fig_table, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"Totale: {len(df)} record analizzati.")

    # Insight
    section_divider()
    st.markdown("### Interpretazione dei Risultati")

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
        'Dettagli tecnici sul processo di analisi, gli strumenti utilizzati e l\'architettura del sistema.</p>',
        unsafe_allow_html=True,
    )

    section_divider()

    # Panoramica della pipeline
    st.markdown("### Come si articola il processo di analisi")

    st.markdown(method_card(
        "1 — Acquisizione dei Media",
        "Il contenuto multimediale (immagini o video) viene caricato tramite l'interfaccia web. "
        "Ai file viene assegnato un UUID univoco che lo possa identificare"
        " e vengono archiviati in Azure Blob Storage. I metadati (ID soggetto, "
        "data di acquisizione, sorgente, contesto) vengono salvati in modo persistente in Azure Table Storage con "
        "l'ID del soggetto (la foto o il video) assegnato PartitionKey e l'UUID assegnato come RowKey. Insieme, PartitionKey e RowKey formano la chiave primaria per "
        "identificare univocamente ogni task di analisi (anche in presenza di più file caricati dallo stesso soggetto)"
    ), unsafe_allow_html=True)

    st.markdown(method_card(
        "2 — Dispatch Asincrono",
        "Il frontend pubblica in Azure Queue Storage un messaggio JSON contenente il riferimento al file "
        "memorizzato nel Blob Storage e gli identificativi necessari al recupero dei metadati. La coda implementa una semantica di consegna at-least-once, "
        "garantendo che ogni task venga elaborato almeno una volta anche in presenza di guasti del worker. Quando un messaggio viene prelevato, "
        "esso diventa temporaneamente invisibile agli altri consumer tramite un meccanismo di visibility timeout (5 minuti); se il worker "
        "completa correttamente l'elaborazione, il messaggio viene eliminato dalla coda, mentre in caso di errore o crash "
        "torna automaticamente disponibile per un nuovo tentativo di elaborazione. Per aumentare l'affidabilità del sistema, i messaggi "
        "che superano una soglia prefissata di tentativi falliti (oltre cinque dequeue) vengono classificati come poison pill e isolati dal "
        "flusso di elaborazione ordinario, consentendo l'analisi e la gestione separata delle anomalie."

    ), unsafe_allow_html=True)

    st.markdown(method_card(
        "3 — Estrazione Frame (Video)",
        "Per limitare il numero di immagini da sottoporre ai servizi di Intelligenza Artificiale, "
        "i video vengono preliminarmente campionati mediante OpenCV, estraendo un fotogramma al secondo. "
        "L'intervallo di campionamento viene calcolato a partire dagli FPS del video, evitando assunzioni rigide "
        "sul frame rate e garantendo risultati coerenti su contenuti eterogenei. L'adozione della tecnica grab/retrieve "
        "permette inoltre di processare esclusivamente i frame di interesse, minimizzando il costo computazionale e migliorando "
        "l'efficienza complessiva del worker asincrono."

    ), unsafe_allow_html=True)

    st.markdown(method_card(
        "4 — Riconoscimento Emotivo tramite IA",
        "Ciascun fotogramma estratto viene sottoposto ad analisi tramite la libreria DeepFace, "
        "utilizzando il modulo dedicato al riconoscimento delle emozioni (emotion analysis). Per ogni frame, "
        "il sistema identifica automaticamente tutti i volti presenti e ne valuta l'espressione facciale mediante un "
        "modello di classificazione emotiva. L'output consiste in una distribuzione probabilistica associata a sette "
        "emozioni fondamentali — felicità, tristezza, rabbia, sorpresa, paura, disgusto e stato neutrale — che rappresenta "
        "il grado di appartenenza del volto a ciascuna categoria emotiva. Oltre alle metriche emozionali, viene registrato "
        "anche il livello di confidenza del rilevamento facciale, consentendo di valutare l'affidabilità delle analisi effettuate."
    ), unsafe_allow_html=True)

    st.markdown(method_card(
        "5 — Persistenza dei Risultati",
        "Al termine dell'elaborazione, i risultati dell'analisi vengono "
        "serializzati in formato JSON e integrati nell'entità corrispondente memorizzata in "
        "Azure Table Storage. L'aggiornamento viene eseguito mediante l'operazione di merge, "
        "che consente di aggiungere o modificare esclusivamente gli attributi relativi all'analisi "
        "senza alterare i metadati originariamente associati al contenuto multimediale. Contestualmente, "
        "il sistema imposta il flag Processed a valore True, segnalando il completamento della pipeline di "
        "elaborazione. Solo dopo la corretta persistenza dei risultati nello storage il messaggio viene rimosso "
        "dalla coda, garantendo che nessun task venga considerato concluso prima che i dati siano stati salvati in modo affidabile."
    ), unsafe_allow_html=True)

    section_divider()

    # Dettagli del modello emotivo
    st.markdown("### Modello di Classificazione delle Emozioni")

    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.markdown("""
        <div class="sci-card">
            <div class="sci-card-header">Specifiche degli strumenti utilizzati e metodologie implementate</div>
            <div style="font-size: 0.88rem; color: var(--text-secondary); line-height: 2;">
                <strong>Framework:</strong> DeepFace<br>
                <strong>Backend:</strong> TensorFlow / Keras<br>
                <strong>Rilevamento:</strong> Su volti singoli o Multi-volto, per-frame. In caso di video l'analisi è effettuata frame by frame<br>
                <strong>Output:</strong> Distribuzione delle probabilità sulle sette emozioni di riferimento (%)<br>
                <strong>Enforcement:</strong> Soft (nessun crash su mancato rilevamento)
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_m2:
        st.markdown("""
        <div class="sci-card">
            <div class="sci-card-header">Studio delle Emozioni</div>
            <div style="font-size: 0.88rem; color: var(--text-secondary); line-height: 2;">
                Basata sulle sei emozioni di base di Ekman più lo stato neutrale.<br><br>
                Felicità · Tristezza · Rabbia · Sorpresa · Paura · Disgusto · Neutrale
            </div>
        </div>
        """, unsafe_allow_html=True)

    section_divider()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ROUTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if "Data Hub" in nav:
    render_dashboard()
elif "Area Input" in nav:
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
