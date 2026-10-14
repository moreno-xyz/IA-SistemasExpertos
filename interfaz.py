"""
Interfaz web – P9 Mesa de ayuda para fallas de red y computadores
Sistema experto basado en casos · Inteligencia Artificial – Grupo B · USAT 2026

Ejecutar:   pip install -r requirements.txt
            streamlit run interfaz.py        (o doble clic en ejecutar.bat en Windows)

Necesita en la misma carpeta: motor_inferencia.py y la carpeta base_conocimientos/

Decisiones de interfaz y su sustento:
 * Inicio y Manual de uso antes de usar el sistema (guía al usuario).
 * El usuario elige síntomas de una lista cerrada; no se interpreta texto libre  [5]; [9] Sec. 3.1; [4] p. 37
 * Se muestran los 3 casos más parecidos con su porcentaje y su solución  [9] Sec. 3.1.1; [3]
 * Explicación «¿por qué?» con el aporte de cada atributo y las fuentes  [9] Sec. 3.3.5
 * Explicación «¿cómo?» con las reglas de adaptación aplicadas  [8] Sec. 6; [9] Sec. 4
 * Cada caso muestra su respaldo documental (fuente técnica Tnn con fragmento literal).
 * Retener y agregar casos exige la clave de administrador y un respaldo documental  [1] p. 9; [8] Sec. 7
 * Aviso: el sistema orienta y no resuelve solo  [1] p. 60

Diseño visual: barra lateral azul noche, encabezado con degradado, pestañas segmentadas, tarjetas con sombra suave,
tipografía Bricolage Grotesque + Figtree, íconos Material Symbols y textos de apoyo plegados.
"""

import html
import re
import sys
from pathlib import Path

import streamlit as st

# Si se ejecuta con el botón ▶ de VS Code (python interfaz.py), se relanza con Streamlit.
if __name__ == "__main__" and not st.runtime.exists():
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", __file__]
    sys.exit(stcli.main())

from motor_inferencia import (NOMBRES_ATRIB, BaseConocimientos, Consulta, MotorInferencia, actualizar_uso_fuentes,
                              agregar_caso, agregar_fuente_tecnica, agregar_sintoma, analisis_sensibilidad, auditar_coherencia,
                              rechazar_caso, validar_caso, validar_loo, verificar_base, verificar_clave,
                              evaluar_casos_prueba)

RUTA_BC = Path(__file__).with_name("base_conocimientos")
RUTA_PRUEBAS = Path(__file__).with_name("validacion") / "casos_prueba.json"


def _leer_pruebas() -> list:
    """Casos de prueba de la validación (si el archivo existe)."""
    try:
        import json
        with open(RUTA_PRUEBAS, encoding="utf-8") as f:
            return json.load(f)["casos"]
    except (OSError, ValueError, KeyError):
        return []
DISPOSITIVOS = ["PC de escritorio", "Laptop"]
SISTEMAS = ["Windows 10", "Windows 11", "Ubuntu 22.04"]
CONEXIONES = ["Cableada", "Wi-Fi"]
UBICACIONES = ["Laboratorio", "Aula", "Oficina administrativa", "Biblioteca", "Auditorio"]
RESPALDA = ["causa y solucion", "causa", "solucion", "sintomas"]
ETIQ_RESPALDA = {"causa y solucion": "causa y solución", "causa": "causa", "solucion": "solución",
                 "sintomas": "síntomas", "causa y solución": "causa y solución", "solución": "solución"}

st.set_page_config(page_title="Mesa de ayuda · Sistema experto P9", page_icon=":material/support_agent:",
                   layout="wide")

# ─────────────────────────────────────────────────────────────────────────────
# Estilo visual
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Figtree:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,300..500,0..1,0&display=block');

:root{
  --ink:#0F1B2D; --ink-2:#44526A; --muted:#7A879B; --line:#E1E6EE; --line-2:#EDF0F5;
  --paper:#F2F5F9; --card:#FFFFFF; --primary:#0A7C7A; --primary-2:#13A39C; --primary-soft:#DDF3F0;
  --clay:#5B4FD1; --clay-soft:#ECE9FC; --ok:#1F9D63; --ok-soft:#DFF5E9; --warn:#B7791F; --warn-soft:#FBF0D9;
  --bad:#C2413A; --bad-soft:#FBE4E1; --navy:#0C1626; --navy-2:#10304A; --radius:18px;
  --ring:0 0 0 1px rgba(15,27,45,.07), 0 8px 20px -14px rgba(15,27,45,.28);
}
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select, label {
  font-family:'Figtree', system-ui, sans-serif !important; }
.stApp { background: var(--paper); color: var(--ink); }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1240px; }
h1, h2, h3, h4 { font-family:'Bricolage Grotesque', 'Figtree', sans-serif !important; color: var(--ink); letter-spacing:-0.02em; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { opacity:.55; }
:focus-visible { outline:2px solid var(--primary-2) !important; outline-offset:2px; }
@media (prefers-reduced-motion: reduce){ *{ transition:none !important; animation:none !important; } }

/* Íconos */
.msr { font-family:'Material Symbols Rounded'; font-weight:400; font-style:normal; font-size:20px; line-height:1;
  letter-spacing:normal; text-transform:none; display:inline-block; white-space:nowrap; direction:ltr;
  -webkit-font-feature-settings:'liga'; font-feature-settings:'liga'; -webkit-font-smoothing:antialiased;
  font-variation-settings:'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; vertical-align:-4px; }
.mono { font-family:'JetBrains Mono', ui-monospace, monospace !important; font-size:.82em; letter-spacing:0; }

/* Encabezado principal */
.hero { position:relative; overflow:hidden; display:flex; align-items:center; gap:22px; margin:0 0 1.5rem;
  padding:30px 34px; border-radius:26px; color:#fff;
  background: radial-gradient(800px 280px at 100% 0%, rgba(19,163,156,.55), transparent 60%),
              linear-gradient(135deg, var(--navy) 0%, var(--navy-2) 55%, #0A5F66 100%); }
.hero::before { content:""; position:absolute; inset:0; pointer-events:none;
  background-image: radial-gradient(rgba(255,255,255,.16) 1.2px, transparent 1.4px); background-size:24px 24px;
  -webkit-mask-image: linear-gradient(90deg, transparent 35%, #000 100%); mask-image: linear-gradient(90deg, transparent 35%, #000 100%); }
.hero > * { position:relative; }
.hero .mark { width:64px; height:64px; border-radius:20px; background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.22);
  display:flex; align-items:center; justify-content:center; flex:0 0 auto; backdrop-filter:blur(6px); }
.hero .mark .msr { font-size:32px; vertical-align:0; color:#fff; }
.hero h1 { color:#fff !important; font-size:2.5rem; font-weight:700; margin:0 0 .3rem; padding:0; line-height:1.08; }
.hero p { color:rgba(255,255,255,.8); margin:0; font-size:1.02rem; max-width:56ch; }
@media (max-width:720px){ .hero { padding:22px; flex-direction:column; align-items:flex-start; } .hero h1 { font-size:1.9rem; } }

/* Pestañas (control segmentado) · solo atributos data-baseweb, que existen en todas las versiones */
[data-baseweb="tab-list"] { display:flex !important; width:100% !important; gap:10px !important; padding:10px !important;
  background:var(--card) !important; border:1px solid var(--line) !important; border-radius:18px !important;
  box-shadow:0 8px 20px -16px rgba(15,27,45,.35) !important; overflow-x:auto; scrollbar-width:none; }
[data-baseweb="tab-list"]::-webkit-scrollbar { display:none; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display:none !important; height:0 !important; opacity:0 !important; }
button[data-baseweb="tab"] { flex:1 1 0 !important; min-width:0; height:48px !important; padding:0 24px !important; margin:0 !important;
  border-radius:12px !important; border:none !important; border-bottom:none !important; background:transparent !important;
  color:var(--ink-2) !important; justify-content:center !important; white-space:nowrap; transition:background .15s, color .15s; }
button[data-baseweb="tab"], button[data-baseweb="tab"]:hover, button[data-baseweb="tab"]:focus, button[data-baseweb="tab"]:focus-visible, button[data-baseweb="tab"]:active { outline:none !important; }
button[data-baseweb="tab"] p, button[data-baseweb="tab"] div { margin:0 !important; font-weight:600 !important; font-size:.93rem !important; color:inherit !important; }
button[data-baseweb="tab"] p { display:inline-flex !important; align-items:center; justify-content:center; gap:10px; }
button[data-baseweb="tab"] span { font-size:20px; }
button[data-baseweb="tab"]:hover { background:var(--line-2) !important; color:var(--ink) !important; }
button[data-baseweb="tab"][aria-selected="true"] { background:linear-gradient(135deg, var(--primary), var(--primary-2)) !important;
  color:#fff !important; box-shadow:0 8px 16px -10px rgba(10,124,122,.9) !important; }
button[data-baseweb="tab"][aria-selected="true"] * { color:#fff !important; }
[data-baseweb="tab-panel"] { padding-top:1.1rem !important; }
[data-baseweb="tab-panel"] [data-baseweb="tab-list"] { background:var(--line-2) !important; border:none !important; box-shadow:none !important; padding:6px !important; gap:6px !important; }
[data-baseweb="tab-panel"] button[data-baseweb="tab"] { height:40px !important; padding:0 16px !important; }
@media (max-width:900px){ button[data-baseweb="tab"] { flex:0 0 auto !important; } }

/* Evita el salto lateral al cambiar de pestaña (barra de desplazamiento siempre reservada) */
html { overflow-y:scroll; scrollbar-gutter:stable; }
[data-testid="stMain"], section.main, .main { scrollbar-gutter:stable; }

/* Títulos de sección */
.sec { display:flex; align-items:center; gap:12px; margin:1.8rem 0 .35rem; }
.sec .num { display:inline-flex; align-items:center; justify-content:center; min-width:30px; height:30px; border-radius:50%;
  background:var(--primary); color:#fff; font-size:.8rem; font-weight:700; }
.sec .ico { display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; border-radius:11px;
  background:var(--primary-soft); color:var(--primary); }
.sec .ico .msr { vertical-align:0; }
.sec h3 { margin:0; font-size:1.3rem; font-weight:700; }
.sec-desc { color:var(--muted); font-size:.9rem; margin:0 0 1rem; }

/* Tarjetas */
.card, .stat, .step { background:var(--card); border-radius:var(--radius); box-shadow:var(--ring); }
.card { padding:20px 22px; }
.stat { padding:18px 20px; height:100%; }
.stat .lbl { color:var(--muted); font-size:.82rem; font-weight:600; display:flex; align-items:center; gap:7px; }
.stat .lbl .msr { color:var(--primary); }
.stat .val { font-family:'Bricolage Grotesque', sans-serif; font-size:2.3rem; font-weight:700; color:var(--ink); margin-top:6px; letter-spacing:-0.03em; line-height:1.1; }
.step { padding:20px; height:100%; }
.step .top { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.step .ic { width:40px; height:40px; border-radius:50%; background:linear-gradient(135deg, var(--primary), var(--primary-2)); color:#fff;
  display:flex; align-items:center; justify-content:center; }
.step .ic .msr { vertical-align:0; }
.step .n { color:var(--muted); font-size:.8rem; font-weight:600; }
.step h4 { margin:0 0 4px; font-size:1.05rem; font-weight:700; }
.step p { margin:0; color:var(--ink-2); font-size:.88rem; line-height:1.55; }
.step .cite { margin-top:12px; color:var(--muted); font-size:.74rem; }

/* Etiquetas */
.pill { display:inline-flex; align-items:center; gap:5px; padding:4px 11px; border-radius:999px; font-size:.77rem;
  font-weight:600; background:var(--line-2); color:var(--ink-2); white-space:nowrap; }
.pill .msr { font-size:15px; vertical-align:0; }
.pill.ok { background:var(--ok-soft); color:#17754A; }
.pill.warn { background:var(--warn-soft); color:#8A5C12; }
.pill.bad { background:var(--bad-soft); color:var(--bad); }
.pill.pri { background:var(--primary-soft); color:#075E5C; }
.pill.clay { background:var(--clay-soft); color:var(--clay); }
.pills { display:flex; flex-wrap:wrap; gap:6px; }

/* Tarjeta de caso */
.case { display:grid; grid-template-columns:150px 1fr; gap:24px; }
@media (max-width:700px){ .case { grid-template-columns:1fr; gap:14px; } }
.case .score .id { font-size:.82rem; color:var(--muted); font-weight:600; }
.case .score .pct { font-family:'Bricolage Grotesque', sans-serif; font-size:2.7rem; font-weight:700; color:var(--primary);
  letter-spacing:-0.04em; line-height:1.05; margin:2px 0 10px; }
.bar { height:6px; background:var(--line-2); border-radius:99px; overflow:hidden; }
.bar > span { display:block; height:100%; background:linear-gradient(90deg, var(--primary), var(--primary-2)); border-radius:99px; }
.case .body .k { color:var(--muted); font-size:.8rem; font-weight:600; margin-bottom:2px; }
.case .body .v { color:var(--ink); font-size:.96rem; margin-bottom:12px; line-height:1.55; }
.case .meta { color:var(--muted); font-size:.82rem; margin-top:8px; }

/* Solución */
.solution { margin-bottom:14px; background:linear-gradient(180deg, #E8F6F4, #FFFFFF 70%); border-radius:var(--radius);
  box-shadow:0 0 0 1px #BFE4DF, 0 10px 24px -16px rgba(10,124,122,.45); padding:20px 24px; border-left:5px solid var(--primary); }
.solution .k { color:var(--primary); font-size:.82rem; font-weight:700; }
.solution .cause { font-size:.96rem; color:var(--ink-2); margin:2px 0 14px; }
.solution .text { font-size:1.1rem; font-weight:600; color:var(--ink); line-height:1.55; }
.note { display:flex; gap:10px; align-items:flex-start; padding:13px 16px; border-radius:14px; font-size:.9rem; line-height:1.5; margin:.6rem 0; }
.note .msr { flex:0 0 auto; vertical-align:0; margin-top:1px; }
.note.info { background:var(--primary-soft); color:#0B4F4D; }
.note.warn { background:var(--warn-soft); color:#7A5114; }
.note.bad { background:var(--bad-soft); color:#8E2F29; }
.note.ok { background:var(--ok-soft); color:#17623F; }
.note.neutral { background:var(--line-2); color:var(--ink-2); }

/* Preguntas */
.q { display:flex; align-items:center; gap:10px; padding:4px 0; }
.q .t { font-weight:600; color:var(--ink); }
.q .s { color:var(--muted); font-size:.78rem; }

/* Fuente / evidencia */
.src { padding:11px 0 13px; border-bottom:1px solid var(--line-2); }
.src:last-child { border-bottom:none; }
.src .h { display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; }
.src .code { font-family:'JetBrains Mono', monospace; font-size:.76rem; color:#075E5C; background:var(--primary-soft); padding:2px 8px; border-radius:7px; }
.src .t { font-weight:600; font-size:.92rem; }
.src a { color:var(--primary); text-decoration:none; font-size:.84rem; font-weight:600; }
.src blockquote { margin:8px 0 4px; padding:2px 0 2px 12px; border-left:3px solid var(--primary-2); color:var(--ink-2); font-size:.9rem; }
.src .m { color:var(--muted); font-size:.82rem; }

/* Lista de verificación */
.chk { display:flex; gap:10px; align-items:flex-start; padding:9px 0; border-bottom:1px solid var(--line-2); font-size:.9rem; }
.chk .msr { font-size:19px; vertical-align:0; }
.chk.ok .msr { color:var(--ok); } .chk.warn .msr { color:var(--warn); } .chk.bad .msr { color:var(--bad); }

/* Componentes de Streamlit */
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:var(--radius) !important; border:none !important; background:var(--card); box-shadow:var(--ring); }
[data-testid="stMetric"] { background:var(--card); border-radius:var(--radius); padding:16px 18px; box-shadow:var(--ring); }
[data-testid="stMetricLabel"] { color:var(--muted); }
[data-testid="stMetricValue"] { font-family:'Bricolage Grotesque', sans-serif; font-weight:700; letter-spacing:-0.03em; }
[data-testid="stExpander"] details { border:none; border-radius:14px; background:var(--card); box-shadow:var(--ring); }
[data-testid="stExpander"] summary { font-weight:600; padding:.7rem 1rem; }
[data-testid="stExpander"] summary:hover { color:var(--primary); }
.stButton > button, .stFormSubmitButton > button { border-radius:12px; font-weight:600; border:1px solid var(--line); background:var(--card);
  color:var(--ink); transition:transform .12s, box-shadow .12s, background .12s; }
.stButton > button:hover, .stFormSubmitButton > button:hover { border-color:var(--primary-2); color:var(--primary); transform:translateY(-1px); }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:linear-gradient(135deg, var(--primary), var(--primary-2));
  border:none; color:#fff; box-shadow:0 8px 18px -10px rgba(10,124,122,.8); }
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover { color:#fff; box-shadow:0 12px 22px -10px rgba(10,124,122,.9); }
[data-baseweb="select"] > div, [data-baseweb="input"] > div, textarea { border-radius:12px !important; background:#fff !important;
  border:1px solid var(--line) !important; transition:border-color .15s, box-shadow .15s; }
[data-baseweb="select"] > div:focus-within, [data-baseweb="input"] > div:focus-within, textarea:focus {
  border-color:var(--primary-2) !important; box-shadow:0 0 0 3px rgba(19,163,156,.18) !important; }
[data-baseweb="tag"] { background:var(--primary-soft) !important; color:#075E5C !important; border-radius:9px !important; }
[data-baseweb="tag"] span { color:#075E5C !important; }
[data-testid="stDataFrame"] { border-radius:14px; overflow:hidden; box-shadow:var(--ring); }
[data-testid="stCaptionContainer"] { color:var(--muted); }
hr { border-color:var(--line) !important; }
[data-testid="stForm"] { border:none; border-radius:var(--radius); background:var(--card); padding:22px 24px; box-shadow:var(--ring); }

/* Barra lateral (oscura) */
[data-testid="stSidebar"] { background:var(--navy); border-right:none; }
[data-testid="stSidebar"] .block-container { padding-top:1.5rem; }
[data-testid="stSidebarCollapseButton"] *, [data-testid="stSidebarHeader"] * { color:#9FB2CC !important; }
.sb-brand { display:flex; gap:12px; align-items:center; margin-bottom:20px; }
.sb-brand .mark { width:42px; height:42px; border-radius:13px; background:linear-gradient(135deg, var(--primary), var(--primary-2)); color:#fff;
  display:flex; align-items:center; justify-content:center; }
.sb-brand .mark .msr { vertical-align:0; font-size:22px; }
.sb-brand b { display:block; font-size:1.02rem; color:#fff; font-family:'Bricolage Grotesque', sans-serif; }
.sb-brand span { color:#8FA3BF; font-size:.78rem; }
.sb-h { color:#7F93B0; font-size:.8rem; font-weight:600; margin:22px 0 8px; }
.kv { display:flex; justify-content:space-between; font-size:.88rem; padding:5px 0; color:#B7C4D8; }
.kv b { color:#fff; }
.w { margin:8px 0; } .w .r { display:flex; justify-content:space-between; font-size:.82rem; color:#B7C4D8; margin-bottom:5px; }
.w .r b { font-weight:600; color:#fff; font-variant-numeric:tabular-nums; }
[data-testid="stSidebar"] .bar { background:rgba(255,255,255,.1); }
.sb-stats { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.sb-stats div { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.09); border-radius:14px; padding:11px 13px; }
.sb-stats span { display:block; color:#8FA3BF; font-size:.76rem; font-weight:600; }
.sb-stats b { font-family:'Bricolage Grotesque', sans-serif; font-size:1.6rem; font-weight:700; color:#fff; letter-spacing:-0.02em; }
[data-testid="stSidebar"] .pill { background:rgba(255,255,255,.09); color:#CFE0F5; }
[data-testid="stSidebar"] .pill.pri { background:rgba(19,163,156,.25); color:#8CEDE4; }
.sb-foot { margin-top:24px; color:#7F93B0; font-size:.78rem; line-height:1.6; }
.footer { color:var(--muted); font-size:.8rem; text-align:center; margin-top:2.5rem; padding-top:1.3rem; border-top:1px solid var(--line); }
/* Refuerzos de componentes (Streamlit recientes) */
button[data-testid^="stBaseButton-secondary"], button[data-testid="stBaseButton-minimal"] {
  border-radius:12px !important; border:1px solid var(--line) !important; background:var(--card) !important; color:var(--ink) !important;
  font-weight:600; min-height:2.6rem; padding:.35rem 1rem !important; transition:transform .12s, border-color .12s, color .12s; }
button[data-testid^="stBaseButton-secondary"]:hover { border-color:var(--primary-2) !important; color:var(--primary) !important; transform:translateY(-1px); }
button[data-testid^="stBaseButton-primary"] { border-radius:12px !important; border:none !important; min-height:2.6rem; padding:.35rem 1.1rem !important;
  background:linear-gradient(135deg, var(--primary), var(--primary-2)) !important; color:#fff !important; font-weight:600;
  box-shadow:0 8px 18px -10px rgba(10,124,122,.8); transition:transform .12s, box-shadow .12s; }
button[data-testid^="stBaseButton-primary"]:hover { transform:translateY(-1px); box-shadow:0 12px 22px -10px rgba(10,124,122,.9); }
button[data-testid^="stBaseButton-primary"] * { color:#fff !important; }
button[data-testid^="stBaseButton"]:disabled { opacity:.5; transform:none; }
button[data-testid^="stBaseButton"] [data-testid="stIconMaterial"] { font-size:20px; margin-right:2px; }
[data-testid="stExpander"] summary { border-radius:14px; gap:8px; }
[data-testid="stExpanderDetails"] { padding:.2rem 1rem 1rem; }
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { font-weight:600; color:var(--ink-2); font-size:.88rem; }
[data-testid="stRadio"] [role="radiogroup"] { gap:.4rem 1.2rem; }
[data-baseweb="popover"] ul, [data-baseweb="menu"] { border-radius:12px !important; }
[data-testid="stAlert"] { border-radius:14px; border:none; }

</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Componentes visuales
# ─────────────────────────────────────────────────────────────────────────────
def h(s: str):
    st.markdown(s, unsafe_allow_html=True)


def esc(s) -> str:
    return html.escape(str(s or ""))


def ic(nombre: str, extra: str = "") -> str:
    return f'<span class="msr" {extra}>{nombre}</span>'


def seccion(titulo: str, icono: str = "", num: str = "", desc: str = ""):
    marca = f'<span class="num">{num}</span>' if num else (f'<span class="ico">{ic(icono)}</span>' if icono else "")
    h(f'<div class="sec">{marca}<h3>{esc(titulo)}</h3></div>' + (f'<p class="sec-desc">{desc}</p>' if desc else ""))


def nota(texto: str, tipo: str = "info", icono: str | None = None):
    icono = icono or {"info": "info", "warn": "warning", "bad": "error", "ok": "check_circle", "neutral": "help"}[tipo]
    h(f'<div class="note {tipo}">{ic(icono)}<div>{texto}</div></div>')


def pill(texto: str, tipo: str = "", icono: str = "") -> str:
    return f'<span class="pill {tipo}">{ic(icono) if icono else ""}{esc(texto)}</span>'


def stat(col, etiqueta: str, valor, icono: str):
    col.markdown(f'<div class="stat"><div class="lbl">{ic(icono)}{esc(etiqueta)}</div><div class="val">{esc(valor)}</div></div>',
                 unsafe_allow_html=True)


def con_original(id_caso: str) -> str:
    """«TK-065 = TK-001» si el ticket es la repetición de otro (mismo diagnóstico)."""
    c = bc.caso(id_caso)
    m_ = re.search(r"TK-\d+", c.origen) if c and c.origen.startswith("Ticket repetido") else None
    return f"{id_caso} = {m_.group(0)}" if m_ else id_caso


def rep_pill(c) -> str:
    """Marca los tickets que repiten una falla ya registrada (mismo diagnóstico en otro equipo)."""
    m_ = re.search(r"TK-\d+", c.origen) if c.origen.startswith("Ticket repetido") else None
    return pill(f"Repetición de {m_.group(0)}", "", "content_copy") if m_ else ""


def estado_pill(estado: str) -> str:
    return {"Validado": pill("Validado", "ok", "verified"),
            "Validado parcialmente": pill("Respaldo parcial", "warn", "rule")}.get(estado, pill(estado, "bad", "pending"))


# ─────────────────────────────────────────────────────────────────────────────
# Carga de la base de conocimientos (se recarga después de cada cambio)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def cargar_motor(_version: int):
    return MotorInferencia(BaseConocimientos(RUTA_BC))


ss = st.session_state
ss.setdefault("version_bc", 0)
ss.setdefault("admin", False)
if not RUTA_BC.exists():
    st.error(f"No se encontró la carpeta «{RUTA_BC.name}». Colóquela en la misma carpeta que interfaz.py.")
    st.stop()
try:
    motor = cargar_motor(ss.version_bc)
except Exception as e:  # archivo JSON dañado o editado a mano con un error
    st.error(f"No se pudo leer la base de conocimientos: {e}")
    st.stop()
bc = motor.bc


def recargar():
    ss.version_bc += 1
    cargar_motor.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades para mostrar fuentes
# ─────────────────────────────────────────────────────────────────────────────
def nombre_fuente(ref: str) -> str:
    f = bc.fuente(ref)
    if not f:
        return ref
    if ref.strip().startswith("T"):
        return f"{f['organizacion']} – {f['titulo']}"
    return f"{f['autores']} ({f['anio']})"


def fuente_md(ref: str) -> str:
    """«[6]» → **[6]** Chen, Qu y Fang (2022) · enlace;  «T12» → **T12** Dell – título · enlace."""
    f = bc.fuente(ref)
    if not f:
        return ref
    rid = ref if ref.startswith("T") else f"[{f['id']}]"
    enlace = f" · [abrir]({f['url']})" if f.get("url") else ""
    return f"**{rid}** {nombre_fuente(ref)}{enlace}"


def refs_en(texto: str) -> list[str]:
    """Extrae las referencias [n] y Tnn que aparecen en un texto, sin repetir y en orden."""
    out = []
    for m in re.finditer(r"\[(\d{1,2})\]|\b(T\d{2,3})\b", texto):
        r = f"[{m.group(1)}]" if m.group(1) else m.group(2)
        if r not in out:
            out.append(r)
    return out


def leyenda_fuentes(textos):
    refs = []
    for t in textos:
        for r in refs_en(t):
            if r not in refs:
                refs.append(r)
    if refs:
        h('<div class="m" style="color:var(--muted);font-size:.78rem;margin-top:8px">'
          + " &nbsp;·&nbsp; ".join(f'<span class="mono">{esc(r)}</span> {esc(nombre_fuente(r))}' for r in refs) + "</div>")


def mostrar_respaldo(caso):
    v = caso.validacion
    h(f'<div class="pills" style="margin-bottom:6px">{estado_pill(caso.estado)}'
      f'<span class="pill">{ic("description")}{esc(v.get("metodo", "") or "Sin método")}</span></div>')
    if not v.get("respaldo"):
        nota("Este caso aún no tiene respaldo documental: no se usa para recomendar.", "warn")
    bloques = []
    for x in v.get("respaldo", []):
        f = bc.fuente(x["fuente"]) or {}
        icono_enlace = ic("open_in_new", 'style="font-size:15px"')
        enlace = f'<a href="{esc(f.get("url", ""))}" target="_blank">{icono_enlace} abrir</a>' if f.get("url") else ""
        cita = f'<blockquote>«{esc(x["evidencia"])}»</blockquote>' if x.get("evidencia") else ""
        bloques.append(
            f'<div class="src"><div class="h"><span class="code">{esc(x["fuente"])}</span>'
            f'<span class="t">{esc(nombre_fuente(x["fuente"]))}</span>{enlace}</div>'
            f'<div class="m">Respalda {esc(ETIQ_RESPALDA.get(x.get("respalda", ""), x.get("respalda", "")))}'
            f'{(" · " + esc(x.get("seccion", ""))) if x.get("seccion") else ""}</div>{cita}'
            f'{("<div class=m>" + esc(x["nota"]) + "</div>") if x.get("nota") else ""}</div>')
    if bloques:
        h("".join(bloques))
    if v.get("limitacion"):
        nota(f"<b>Respaldo parcial.</b> {esc(v['limitacion'])}", "warn", "rule")
    if v.get("observacion"):
        st.caption(f"Ajuste respecto de la versión anterior: {v['observacion']}")


# ─────────────────────────────────────────────────────────────────────────────
# Barra lateral
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    h(f'<div class="sb-brand"><div class="mark">{ic("support_agent")}</div>'
      '<div><b>Sistema experto P9</b><span>Razonamiento basado en casos</span></div></div>')
    h(f'<div class="sb-stats"><div><span>Activos</span><b>{len(bc.casos_activos)}</b></div>'
      f'<div><span>Pendientes</span><b>{len(bc.casos_pendientes)}</b></div></div>')
    h('<div class="sb-h">Parámetros</div>'
      f'<div class="kv"><span>Casos mostrados</span><b>{bc.k}</b></div>'
      f'<div class="kv"><span>Umbral mínimo</span><b>{bc.umbral_minimo:.0%}</b></div>'
      f'<div class="kv"><span>Umbral de retención</span><b>{bc.umbral_retencion:.0%}</b></div>')
    h('<div class="sb-h">Pesos de la similitud</div>' + "".join(
        f'<div class="w"><div class="r"><span>{esc(NOMBRES_ATRIB[a])}</span><b>{w:.2f}</b></div>'
        f'<div class="bar"><span style="width:{w * 100:.0f}%"></span></div></div>' for a, w in bc.pesos.items()))
    h('<div class="sb-h">Sesión</div>'
      + (pill("Administrador", "pri", "lock_open") if ss.admin else pill("Sin sesión de administrador", "", "lock")))
    h('<div class="sb-foot">El sistema orienta a partir de casos resueltos y validados. La decisión final '
      'la toma el técnico de soporte; no ejecuta acciones en el equipo ni guarda datos personales.</div>')

h(f'''<div class="hero"><div class="mark">{ic("support_agent")}</div><div>
  <h1>Mesa de ayuda</h1>
  <p>Diagnóstico de fallas de red y computadores, con cada sugerencia respaldada por su fuente.</p>
</div></div>''')

(tab_inicio, tab_manual, tab_ticket, tab_base, tab_admin, tab_valid, tab_fuentes) = st.tabs(
    [":material/home: Inicio", ":material/menu_book: Manual de uso", ":material/confirmation_number: Nuevo ticket",
     ":material/database: Base de casos", ":material/admin_panel_settings: Administrar",
     ":material/monitoring: Validación", ":material/library_books: Fuentes"])

# ═════════════════════════════════════════════════════════════════════════════
# 0. INICIO
# ═════════════════════════════════════════════════════════════════════════════
with tab_inicio:
    seccion("Qué hace este sistema", "lightbulb")
    h('<div class="card" style="font-size:.98rem;line-height:1.7;color:var(--ink-2)">'
      'El técnico registra un ticket con la categoría, el equipo y hasta tres síntomas de una lista cerrada. '
      'El sistema busca los tickets resueltos y <b style="color:var(--ink)">validados</b> que comparten esos síntomas, '
      'propone la causa y la solución del más parecido —adaptada al equipo— y avisa cuándo escalar. '
      'Si los síntomas no bastan, <b style="color:var(--ink)">pregunta</b> en lugar de adivinar. '
      'Cada sugerencia muestra por qué se eligió y qué fuente la respalda.</div>')

    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    stat(m1, "Tickets validados", len(bc.casos_activos), "inventory_2")
    stat(m2, "Fallas distintas", len({c.causa for c in bc.casos_activos}), "category")
    stat(m3, "Síntomas en el catálogo", len(bc.sintoma_nombre), "checklist")
    stat(m4, "Fuentes técnicas", len(bc.tecnicas), "link")

    seccion("Cómo razona", "sync", desc="Ciclo de cuatro pasos de Aamodt y Plaza [8].")
    pasos = [("search", "01", "Recuperar", "Compara el ticket con los casos validados de su subcategoría y elige los más similares.",
              "[6] Ec. 5 · [3] Ec. 2 · [9] 3.1.1"),
             ("tune", "02", "Reutilizar", "Copia la solución del caso más parecido y la adapta al equipo; indica si hay que escalar.",
              "[8] Sec. 6 · [9] Sec. 4 · [4] p. 38"),
             ("fact_check", "03", "Revisar", "El técnico aplica la solución y confirma si funcionó con la conformidad del usuario.",
              "[8] Sec. 7 · [4] p. 49"),
             ("save", "04", "Retener", "Con la clave de administrador guarda el caso, que espera su respaldo antes de usarse.",
              "[7] 3.4–3.5 · [1] p. 9 · [11]")]
    for col, (icono, n, t, d, ci) in zip(st.columns(4), pasos):
        col.markdown(f'<div class="step"><div class="top"><div class="ic">{ic(icono)}</div><span class="n">{n}</span></div>'
                     f'<h4>{t}</h4><p>{d}</p><div class="cite">{ci}</div></div>', unsafe_allow_html=True)

    seccion("Cómo se validó la base", "verified")
    h('<div class="card" style="font-size:.93rem;line-height:1.7;color:var(--ink-2)">'
      'Sin un técnico experto disponible, cada caso se validó con <b style="color:var(--ink)">documentación técnica oficial</b> '
      '(Microsoft, Dell, Epson, Brother, Lenovo, Logitech, Cisco, Google, Mozilla, Ubuntu, CISA, INCIBE, entre otras). '
      'Cada caso guarda su fuente, la sección y un fragmento literal. Cada falla tiene al menos dos tickets (el original y su '
      'repetición en otro equipo), como en una mesa de ayuda real. Los métodos del motor se justifican con las fuentes '
      'académicas [1]–[12]; los valores numéricos se contrastan en la pestaña Validación, con la validación dejando un caso '
      f'fuera y {len(_leer_pruebas())} casos de prueba que no están en la base.</div>')

    seccion("Fuentes utilizadas", "library_books")
    with st.expander(f"Fuentes metodológicas · {len(bc.metodologicas)}", icon=":material/school:"):
        st.caption("[1]–[11] corresponden a los archivos cita 1 … cita 11; [12] es nueva.")
        for f in bc.fuentes_json["metodologicas"]:
            enlace = f' <a href="{esc(f["url"])}" target="_blank">enlace</a>' if f.get("url") else ""
            h(f'<div class="src"><div class="h"><span class="code">[{esc(f["id"])}]</span>'
              f'<span style="font-size:.88rem">{esc(f["ieee"])}</span>{enlace}</div>'
              f'<div class="m">{esc(f["justifica"])}</div></div>')
    por_org = {}
    for t in bc.fuentes_json["tecnicas"]:
        por_org.setdefault(t["organizacion"], []).append(t)
    with st.expander(f"Fuentes técnicas · {len(bc.tecnicas)}", icon=":material/link:"):
        for org, lista in sorted(por_org.items(), key=lambda kv: -len(kv[1])):
            h(f'<div class="sb-h" style="margin-top:14px">{esc(org)} · {len(lista)}</div>')
            for t in lista:
                usos = ", ".join(t.get("casos", []) + t.get("reglas", []))
                h(f'<div class="src"><div class="h"><span class="code">{esc(t["id"])}</span>'
                  f'<a href="{esc(t["url"])}" target="_blank" class="t" style="color:var(--ink)">{esc(t["titulo"])}</a>'
                  f'<span class="m">{esc(t["anio"])} · {esc(t["idioma"])}</span></div>'
                  f'<div class="m">Usada en: {esc(usos or "—")}</div></div>')

    h('<div class="footer">Universidad Católica Santo Toribio de Mogrovejo · Ingeniería de Sistemas y Computación · '
      'Inteligencia Artificial – Grupo B<br>Docente: Villegas Cubas, Juan Elías · Integrantes: Timana Novoa, Juan Diego; '
      'Seminario Bautista, Lorena Marialya · Chiclayo, 2026</div>')

# ═════════════════════════════════════════════════════════════════════════════
# 1. MANUAL DE USO
# ═════════════════════════════════════════════════════════════════════════════
with tab_manual:
    seccion("Manual de uso", "menu_book", desc="Lea esta guía antes de usar el sistema. Cada sección corresponde a una pestaña.")

    with st.expander("Antes de empezar", icon=":material/flag:", expanded=True):
        st.markdown(f"""
- **Para quién es:** el técnico de soporte de 1.er nivel (o un practicante) que atiende fallas de red y de computadores.
- **Qué hace:** sugiere la causa probable y la solución a partir de los **{len(bc.casos_activos)} casos validados**, con su explicación y sus fuentes.
- **Qué no hace:** no interpreta texto libre, no ejecuta acciones en el equipo y no reemplaza al técnico.
- **Alcance:** PC y laptops con Windows 10, Windows 11 o Ubuntu 22.04; fallas de red, hardware, software y cuentas. Quedan fuera servidores, redes troncales, reparación electrónica y móviles.
""")
    with st.expander("Registrar un ticket", icon=":material/confirmation_number:"):
        st.markdown("""
1. Elija la **categoría** y la **subcategoría** de la falla (por ejemplo, *Red › Wi-Fi*).
2. Marque el **dispositivo**, el **sistema operativo** y la **conexión a la red**.
3. Elija **de 1 a 3 síntomas**. Por defecto se ofrecen los de la subcategoría elegida; puede ampliar la lista a toda la categoría o a todas.
   - Elija al menos un **síntoma de falla** (por ejemplo, «El periférico se apaga o se desconecta solo»).
   - Los marcados como **dato adicional** (por ejemplo, «Periférico con cable USB») no son fallas: ayudan a distinguir la causa.
   - Algunas subcategorías fijan la conexión o el dispositivo: *Wi-Fi* fija conexión Wi-Fi, *Conectividad cableada* fija conexión cableada y *Batería* fija laptop. No se ofrecen síntomas imposibles para su equipo.
   - Elija la subcategoría del **equipo que falla**: un mouse, audífono o teclado va en *Hardware › Periféricos*; «La computadora se apaga sola» va en *Hardware › Estabilidad*.
4. Presione **Buscar casos similares**. El botón **Cargar ejemplo** llena un ticket de prueba.
""")
    with st.expander("Leer los resultados", icon=":material/analytics:"):
        st.markdown(f"""
- Se muestran hasta **{bc.k} tickets resueltos** que comparten síntomas, ordenados por **similitud** (0 % nada en común; 100 % idéntico).
- **¿Por qué se sugiere?** detalla el aporte de cada dato a la similitud. **Respaldo documental** muestra la fuente oficial con su fragmento literal.
- Se busca primero en **la misma subcategoría** y solo con soluciones que aplican a su sistema operativo, conexión y dispositivo.
- Si ningún caso comparte síntomas o no llega al **{bc.umbral_minimo:.0%}**, no se propone solución y se recomienda escalar.
- **Si el sistema pregunta:** sus síntomas coinciden con varias fallas. Responda con **Sí, agregar** y el sistema vuelve a buscar.
- **Si dice que ningún caso explica todos los síntomas juntos:** puede haber registrado dos problemas a la vez (registre un ticket por cada uno) o una falla que la base aún no tiene (escale).
- **Síntoma «inferido»:** el sistema deduce un síntoma general de uno que usted marcó (por ejemplo, «IP 169.254.x.x» supone «Sin acceso a internet»).
- **«El caso supone…»:** el caso propuesto asume un dato que usted no indicó; compruébelo antes de aplicar la solución.
""")
    with st.expander("Solución propuesta y escalamiento", icon=":material/build:"):
        st.markdown("""
- La solución es la del caso más parecido, **adaptada** si su equipo es distinto:
  - **R1** cambia los comandos de Windows por los de Ubuntu (o al revés), por ejemplo `ipconfig /flushdns` → `resolvectl flush-caches`.
  - **R2** cambia la revisión del cable por la del Wi-Fi (o al revés).
  - **R3** cambia la fuente de poder por el cargador o la batería (o al revés).
- **Escalar a 2.º nivel** aparece cuando el caso se resolvió en 2.º nivel (**R4**) o cuando marcó *Varios usuarios con el mismo fallo* (**R5**).
- **Justificación de la decisión** resume, paso por paso, qué fuente respalda cada decisión.
""")
    with st.expander("Revisión del técnico y aprendizaje", icon=":material/fact_check:"):
        st.markdown("""
1. Indique si la solución **funcionó** y si el usuario dio su **conformidad**.
2. Corrija, si hace falta, la causa, la solución, el objeto del fallo, el tiempo y el nivel.
3. Escriba la **clave de administrador** y presione **Registrar revisión**:
   - si existe un caso casi idéntico (≥ 90 %) con la misma solución, se le suma un éxito;
   - si no, se crea un caso **Pendiente**, que no se usa para recomendar hasta tener su fuente de respaldo.
4. Si la solución no funcionó, el ticket no se guarda y debe escalarse.
""")
    with st.expander("Administrar casos", icon=":material/admin_panel_settings:"):
        st.markdown("""
Con la **clave de administrador** puede:
- **Agregar caso** con su fuente de respaldo (fuente, sección, fragmento literal y nota). Sin fuente queda *Pendiente*. Se rechazan duplicados.
- **Validar pendientes**: agregar la fuente a los casos retenidos o eliminarlos.
- **Agregar fuente**: registrar una página oficial nueva, comprobando antes que contiene el respaldo.
- **Agregar síntoma**: ampliar el catálogo cerrado.

Cierre la sesión al terminar.
""")
    with st.expander("Validación y verificación", icon=":material/monitoring:"):
        st.markdown("""
- **Validación dejando un caso fuera:** cada ticket de la base se usa como ticket nuevo contra el resto; acierta si recupera el mismo diagnóstico.
- **Casos de prueba:** tickets simulados que no están en la base (típicos, difíciles y límite), con la respuesta esperada definida antes de ejecutar el sistema.
- **Análisis de sensibilidad:** cómo cambia el resultado con otros pesos o umbrales.
- **Auditoría de coherencia:** prueba miles de combinaciones y comprueba que ninguna propuesta sea incoherente.
- **Verificación de la base:** respaldos, fuentes, duplicados y catálogo.
""")
    with st.expander("Problemas frecuentes", icon=":material/help:"):
        st.markdown("""
- **«No se encontró la carpeta base_conocimientos»:** debe estar junto a `interfaz.py` y `motor_inferencia.py`.
- **«streamlit no se reconoce como comando»:** use `python -m streamlit run interfaz.py`.
- **El botón Buscar está desactivado:** elija al menos un síntoma.
- **«Clave de administrador incorrecta»:** la base no se modificó; la clave distingue mayúsculas.
- **Editó un JSON a mano y la app no abre:** revise comas y comillas, o restaure la copia original.
""")

# ═════════════════════════════════════════════════════════════════════════════
# 2. NUEVO TICKET
# ═════════════════════════════════════════════════════════════════════════════
cats = {c["codigo"]: c["categoria"] for c in bc.categorias_json["categorias"] if c["subcategoria"] is None}


ALCANCES = ["Esta subcategoría", "Toda la categoría", "Todas las categorías"]
sint_por_sub = {}
for _c in bc.casos_activos:
    for _s in _c.registrados:
        sint_por_sub.setdefault(_c.codigo_cat, set()).add(_s)


def cargar_ejemplo():
    ss.t_cat, ss.t_sub, ss.t_disp, ss.t_so, ss.t_con = "1", "1.5", "PC de escritorio", "Windows 11", "Cableada"
    ss.t_alcance = ALCANCES[0]
    ss.t_sint = ["S118", "S119"]
    ss.auto_buscar = True


def agregar_sintoma_ticket(cod):
    """Respuesta a una pregunta del sistema: agrega el síntoma al ticket y vuelve a buscar [8] Sec. 5; [9] Sec. 3.3.5."""
    actuales = list(ss.get("t_sint", []))
    if cod not in actuales and len(actuales) < 3:
        actuales.append(cod)
    if cod not in sint_por_sub.get(ss.get("t_sub"), set()):
        ss.t_alcance = ALCANCES[2]
    ss.t_sint = actuales
    ss.auto_buscar = True


with tab_ticket:
    cab1, cab2 = st.columns([5, 1])
    with cab1:
        seccion("Describa la falla", num="01", desc="Elija los datos de las listas; los síntomas vienen de un catálogo cerrado [5].")
    with cab2:
        st.write("")
        st.button("Cargar ejemplo", on_click=cargar_ejemplo, icon=":material/auto_awesome:", width="stretch",
                  help="PC con Windows 11: un periférico con cable USB se desconecta solo")

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            cat_cod = st.selectbox("Categoría", list(cats), format_func=lambda c: f"{c} · {cats[c]}", key="t_cat")
            subs = [c for c in bc.subcategoria_de if c.startswith(cat_cod + ".")]
            if ss.get("t_sub") not in subs:
                ss.t_sub = subs[0]
            sub_cod = st.selectbox("Subcategoría", subs, format_func=lambda c: f"{c} · {bc.subcategoria_de[c]}", key="t_sub")
            # La subcategoría puede exigir una conexión o un dispositivo (p. ej. Wi-Fi → conexión Wi-Fi; Batería → laptop)
            req = bc.sub_requiere.get(sub_cod, {})
            if "dispositivo" in req:
                ss.t_disp = req["dispositivo"]
            if "conexion" in req:
                ss.t_con = req["conexion"]
            dispositivo = st.radio("Dispositivo", DISPOSITIVOS, horizontal=True, key="t_disp", disabled="dispositivo" in req,
                                   help="Fijado por la subcategoría elegida" if "dispositivo" in req else None)
        with col2:
            so = st.selectbox("Sistema operativo", SISTEMAS, key="t_so")
            conexion = st.radio("Conexión a la red", CONEXIONES, horizontal=True, key="t_con", disabled="conexion" in req,
                                help="Fijada por la subcategoría elegida" if "conexion" in req else "Cómo se conecta el equipo a la red")
            alcance = st.radio("Mostrar síntomas de", ALCANCES, horizontal=True, key="t_alcance")

        if alcance == ALCANCES[0]:
            opciones = [c for c in bc.sintoma_nombre if c in sint_por_sub.get(sub_cod, set())]
        elif alcance == ALCANCES[1]:
            opciones = [c for c in bc.sintoma_nombre if bc.sintoma_grupo.get(c) == cats[cat_cod]]
        else:
            opciones = list(bc.sintoma_nombre)
        # se ocultan los síntomas que no pueden darse con esta conexión o dispositivo (p. ej. «Señal Wi-Fi débil» en cable)
        actual = {"conexion": conexion, "dispositivo": dispositivo}
        opciones = [c for c in opciones if all(actual[k] == v for k, v in bc.sintoma_requiere.get(c, {}).items())]
        # primero los síntomas de falla, luego los datos de contexto
        opciones.sort(key=lambda c: (bc.sintoma_tipo.get(c) == "contexto", int(c[1:])))
        ss.t_sint = [s for s in ss.get("t_sint", []) if s in opciones]
        sintomas = st.multiselect("Síntomas (de 1 a 3)", opciones, max_selections=3, key="t_sint",
                                  format_func=lambda c: f"{bc.sintoma_nombre[c]}  ({c})"
                                  + ("  · dato adicional" if bc.sintoma_tipo.get(c) == "contexto" else ""),
                                  placeholder="Escriba para buscar un síntoma",
                                  help="Elija al menos un síntoma de falla. Los «datos adicionales» solo afinan la búsqueda.")
        if req:
            h('<div class="pills">' + "".join(
                pill(f"{'Conexión' if k == 'conexion' else 'Dispositivo'}: {v}", "pri", "lock") for k, v in req.items())
              + f'<span class="pill">Fijado por «{esc(bc.subcategoria_de[sub_cod])}»</span></div>')

        buscar = st.button("Buscar casos similares", type="primary", disabled=not sintomas, icon=":material/search:")
    if ss.pop("auto_buscar", False) and sintomas:
        buscar = True
    if buscar:
        q = Consulta(codigo_cat=sub_cod, dispositivo=dispositivo, so=so, conexion=conexion, sintomas=set(sintomas))
        ss.consulta = q
        ss.salida = motor.resolver(q)
        ss.pop("retencion", None)

    salida, q = ss.get("salida"), ss.get("consulta")
    if salida and q:
        # si la base cambió, se recalcula con los casos vigentes
        if any(bc.caso(r.caso.id) is None for r in salida["sugerencias"]):
            salida = ss.salida = motor.resolver(q)
        n_sug = len(salida["sugerencias"])
        nivel_txt = {"subcategoria": f"Misma subcategoría · {bc.subcategoria_de.get(q.codigo_cat, '')}",
                     "categoria": "Sin casos en la subcategoría · se buscó en la categoría",
                     "toda la base": "Sin casos en la categoría · se buscó en toda la base"}.get(salida.get("nivel_busqueda", ""), "")
        seccion("Tickets resueltos que comparten síntomas", num="02",
                desc=(esc(nivel_txt) + " &nbsp;·&nbsp; <span class='mono'>[7] 3.2 · [8] Sec. 5</span>") if n_sug else "")
        if not n_sug:
            nota("Ningún caso validado comparte un síntoma de falla con este ticket.", "neutral", "search_off")
        for i, r in enumerate(salida["sugerencias"], 1):
            c = r.caso
            otra = c.codigo_cat != q.codigo_cat
            with st.container(border=True):
                h(f'''<div class="case">
                  <div class="score"><div class="id">#{i} · {esc(c.id)}</div>
                    <div class="pct">{r.similitud:.0%}</div>
                    <div class="bar"><span style="width:{r.similitud * 100:.0f}%"></span></div>
                    <div class="meta">similitud</div></div>
                  <div class="body">
                    <div class="pills" style="margin-bottom:12px">{estado_pill(c.estado)}{rep_pill(c)}
                      {pill(f"{c.categoria} › {c.subcategoria}", "clay" if otra else "", "warning" if otra else "category")}
                      {pill(c.dispositivo, "", "computer")}{pill(c.so, "", "terminal")}{pill(c.conexion, "", "lan" if c.conexion == "Cableada" else "wifi")}</div>
                    <div class="k">Causa</div><div class="v">{esc(c.causa)}</div>
                    <div class="k">Solución aplicada</div><div class="v" style="margin-bottom:0">{esc(c.solucion)}</div>
                    <div class="meta">{esc(c.nivel)} · {c.tiempo_min:.0f} min · aplicada con éxito {c.veces_exito} {"vez" if c.veces_exito == 1 else "veces"}</div>
                  </div></div>''')
                e1, e2 = st.columns(2)
                with e1.expander("¿Por qué se sugiere?", icon=":material/query_stats:"):
                    comunes = [bc.sintoma_nombre[s] for s in sorted((q.registrados or q.sintomas) & c.sintomas)]
                    inferidos = [bc.sintoma_nombre[s] for s in sorted((q.sintomas & c.sintomas) - (q.registrados or set()))]
                    h('<div class="pills" style="margin-bottom:10px">'
                      + ("".join(pill(x, "pri", "check") for x in comunes) or pill("Sin síntomas en común"))
                      + "".join(pill(f"{x} · inferido", "", "subdirectory_arrow_right") for x in inferidos)
                      + "</div>")
                    if inferidos:
                        st.caption("«Inferido»: síntoma general que se deduce de uno marcado (p. ej. «IP 169.254.x.x» "
                                   "supone «Sin acceso a internet»)  ·  [8] Sec. 5")
                    st.dataframe([{"Atributo": NOMBRES_ATRIB[k], "Similitud": round(loc, 2), "Peso": round(bc.pesos[k], 2),
                                   "Aporte": round(ap, 3), "Método": bc.atributos[k]["fuente_metodo"]}
                                  for k, (loc, ap) in r.detalle.items()], hide_index=True, width="stretch")
                    st.caption(f"Similitud global = suma de aportes = {r.similitud:.3f}  ([6] Ec. 5)")
                with e2.expander("Respaldo documental", icon=":material/verified:"):
                    mostrar_respaldo(c)

        seccion("Solución propuesta", num="03")
        p = salida["propuesta"]
        if salida.get("aviso"):
            nota(esc(salida["aviso"]), "warn")
        if p is None:
            if salida.get("preguntas"):
                nota(esc(salida["mensaje"]), "info", "help")
                with st.container(border=True):
                    h('<div class="k" style="color:var(--muted);font-size:.72rem;font-weight:700;'
                      'margin-bottom:6px">Para distinguir la causa</div>')
                    for n_pr, pr in enumerate(salida["preguntas"]):
                        c1_, c2_ = st.columns([5, 1])
                        c1_.markdown(f'<div class="q">{ic("help_outline")}<span class="t">{esc(pr["pregunta"])}</span>'
                                     f'<span class="s">{esc(", ".join(pr["casos"]))}</span></div>', unsafe_allow_html=True)
                        c2_.button("Sí, agregar", key=f"preg_{n_pr}_{pr['codigo']}", on_click=agregar_sintoma_ticket,
                                   args=(pr["codigo"],), icon=":material/add:", width="stretch",
                                   disabled=len(ss.get("t_sint", [])) >= 3 or pr["codigo"] in ss.get("t_sint", []))
                    if len(ss.get("t_sint", [])) >= 3:
                        st.caption("Ya eligió 3 síntomas: quite uno para agregar otro.")
                st.caption("Pedir datos en vez de adivinar: [8] Sec. 5, p. 16 · [9] Sec. 3.3.5 · [7] p. 5")
            else:
                nota(esc(salida["mensaje"]), "bad", "report")
                st.caption("Umbral de recuperación [8] Sec. 5 · escalamiento [4] p. 38; [1] p. 60")
        else:
            if p["escalar_2do_nivel"]:
                nota("Este caso requiere <b>2.º nivel</b>: registre el diagnóstico y derive el ticket.", "warn", "escalator_warning")
            h(f'''<div class="solution">
                <div class="pills" style="margin-bottom:10px">{pill("Caso base " + p["caso"], "pri", "inventory_2")}</div>
                <div class="k">Causa probable</div><div class="cause">{esc(p["causa_probable"])}</div>
                <div class="k">Qué hacer</div><div class="text">{esc(p["solucion"])}</div></div>''')
            for alt in p.get("alternativas", []):
                nota(f"<b>Si no funciona:</b> {esc(alt['caso'])} tiene los mismos síntomas con otra causa "
                     f"(<i>{esc(alt['causa'])}</i>). {esc(alt['solucion'])}", "neutral", "alt_route")
            for nt in p.get("notas", []):
                st.caption(f"Si además hay {', '.join('«' + x + '»' for x in nt['si_ademas'])}, revise {nt['caso']} "
                           f"({nt['causa']}).")
            with st.expander("¿Cómo se obtuvo esta solución?", icon=":material/account_tree:"):
                for x in p["reglas"]:
                    h(f'<div class="src"><div class="h"><span class="code">{esc(x["regla"])}</span>'
                      f'<span class="t">{esc(x["texto"])}</span></div>'
                      f'<div class="m mono">{esc("; ".join(x["fuentes"]))}</div></div>')
                leyenda_fuentes(f for x in p["reglas"] for f in x["fuentes"])

        with st.expander("Justificación completa de la decisión", icon=":material/gavel:"):
            just = motor.justificar(q, salida)
            for paso in just["pasos"]:
                st.markdown(f"**{paso['paso']}.** {paso['decision']}")
                for f in paso.get("fuentes", []):
                    h(f'<div class="m mono" style="color:var(--muted);padding-left:14px">{esc(f)}</div>')
                for x in paso.get("respaldo", []):
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{fuente_md(x['fuente'])} — {x.get('seccion', '')}")
                    if x.get("evidencia"):
                        st.markdown(f"> «{x['evidencia']}»")
                if paso.get("limitacion"):
                    st.caption(f"Limitación: {paso['limitacion']}")
            leyenda_fuentes(f for paso in just["pasos"] for f in paso.get("fuentes", []))

        seccion("Revisión del técnico", num="04")
        caso_base = bc.caso(p["caso"]) if p else None
        with st.form("revision"):
            c1, c2 = st.columns(2)
            funciono = c1.radio("¿La solución funcionó?", ["Sí", "No"], horizontal=True)
            conformidad = c2.radio("¿El usuario dio su conformidad?", ["Sí", "No"], horizontal=True)
            causa = st.text_input("Causa final", value=(caso_base.causa if caso_base else ""))
            solucion = st.text_area("Solución aplicada", value=(p["solucion"] if p else ""))
            c3, c4, c5 = st.columns(3)
            objeto = c3.text_input("Objeto del fallo", value=(caso_base.objeto_fallo if caso_base else ""))
            tiempo = c4.number_input("Tiempo de resolución (min)", min_value=1, value=10)
            nivel = c5.selectbox("Nivel de resolución", ["1.er nivel", "2.º nivel"])
            clave = st.text_input("Clave de administrador (para guardar el caso)", type="password")
            enviar = st.form_submit_button("Registrar revisión", icon=":material/task_alt:")
        if enviar:
            rev = motor.revisar(funciono == "Sí", conformidad == "Sí")
            if rev["estado"] != "Confirmado":
                ss.retencion = ("warning", "No se retiene: " + rev["accion"].lower() + "  ([4] p. 49; [4] p. 38)")
            elif not causa.strip() or not solucion.strip():
                ss.retencion = ("error", "Complete la causa final y la solución aplicada antes de retener el caso.")
            elif not verificar_clave(clave):
                ss.retencion = ("error", "Clave de administrador incorrecta: el caso no se guardó.")
            else:
                msg = motor.retener(q, causa, solucion, objeto, tiempo, nivel, clave=clave)
                ss.retencion = ("success", msg)
                recargar()
                st.rerun()
        if ss.get("retencion"):
            tipo, msg = ss.retencion
            getattr(st, tipo)(msg)

# ═════════════════════════════════════════════════════════════════════════════
# 3. BASE DE CASOS
# ═════════════════════════════════════════════════════════════════════════════
with tab_base:
    seccion("Base de casos", "database", desc="Cada caso guarda su respaldo documental; los códigos T están en Fuentes.")
    f1, f2 = st.columns(2)
    filtro = f1.multiselect("Filtrar por categoría", sorted({c.categoria for c in bc.casos}), placeholder="Todas")
    filtro_est = f2.multiselect("Filtrar por estado", ["Validado", "Validado parcialmente", "Pendiente"], placeholder="Todos")
    visibles = [c for c in bc.casos if (not filtro or c.categoria in filtro) and (not filtro_est or c.estado in filtro_est)]
    st.dataframe([{"ID": c.id, "Categoría": c.categoria, "Subcategoría": c.subcategoria, "Dispositivo": c.dispositivo,
                   "SO": c.so, "Conexión": c.conexion,
                   "Síntomas": "; ".join(bc.sintoma_nombre.get(s, s) for s in sorted(c.registrados)),
                   "Causa": c.causa, "Solución": c.solucion, "Nivel": c.nivel, "Éxitos": c.veces_exito,
                   "Estado": c.estado, "Fuentes": ", ".join(x["fuente"] for x in c.validacion.get("respaldo", [])),
                   "Origen": ("Repetición de " + re.search(r"TK-\d+", c.origen).group(0))
                             if c.origen.startswith("Ticket repetido") else "Original"}
                  for c in visibles], width="stretch", hide_index=True)
    st.caption("Cada falla tiene al menos dos tickets: el original y su repetición en otro equipo (mismo diagnóstico y "
               "mismo respaldo), como en una mesa de ayuda real. Así la validación dejando un caso fuera mide el diagnóstico.")

    seccion("Detalle del caso", "manage_search")
    if visibles:
        sel = st.selectbox("Caso", [c.id for c in visibles],
                           format_func=lambda i: f"{i} · {bc.caso(i).subcategoria} · {bc.caso(i).causa}")
        c = bc.caso(sel)
        a, b = st.columns(2)
        with a:
            h(f'''<div class="card" style="height:100%"><div class="pills" style="margin-bottom:12px">{pill("Problema", "pri", "report_problem")}
              {pill(f"{c.codigo_cat} {c.categoria} › {c.subcategoria}", "", "category")}</div>
              <div class="pills" style="margin-bottom:12px">{pill(c.dispositivo, "", "computer")}{pill(c.so, "", "terminal")}{pill(c.conexion, "", "lan")}</div>
              <div class="k" style="color:var(--muted);font-size:.72rem;font-weight:700;">Síntomas</div>
              <div style="margin:4px 0 12px">{"<br>".join(f"{esc(bc.sintoma_nombre.get(s, s))} <span class='mono' style='color:var(--muted)'>{s}</span>" for s in sorted(c.registrados))}</div>
              <div style="color:var(--muted);font-size:.84rem">{esc(c.tipo_caso)} · {esc(c.ubicacion or "—")} · prioridad {esc(c.prioridad or "—")}<br>
              Efecto percibido: {esc(c.efecto or "—")}</div></div>''')
        with b:
            h(f'''<div class="card" style="height:100%"><div class="pills" style="margin-bottom:12px">{pill("Solución", "ok", "build")}
              {pill(c.nivel, "", "stairs")}{pill(f"{c.tiempo_min:.0f} min", "", "schedule")}</div>
              <div class="k" style="color:var(--muted);font-size:.72rem;font-weight:700;">Objeto del fallo</div>
              <div style="margin:2px 0 10px">{esc(c.objeto_fallo)}</div>
              <div class="k" style="color:var(--muted);font-size:.72rem;font-weight:700;">Causa</div>
              <div style="margin:2px 0 10px">{esc(c.causa)}</div>
              <div class="k" style="color:var(--muted);font-size:.72rem;font-weight:700;">Solución</div>
              <div style="margin:2px 0 10px;font-weight:600">{esc(c.solucion)}</div>
              <div style="color:var(--muted);font-size:.84rem">{esc(c.resultado)} · éxitos: {c.veces_exito}</div></div>''')
        st.write("")
        with st.container(border=True):
            h(f'<div class="sec" style="margin:0 0 6px">{ic("verified")}<h3 style="font-size:1rem">Validación y respaldo documental</h3></div>')
            mostrar_respaldo(c)

# ═════════════════════════════════════════════════════════════════════════════
# 4. ADMINISTRAR CASOS (protegido con clave)
# ═════════════════════════════════════════════════════════════════════════════
def editor_respaldo(prefijo: str, obligatorio: bool = True):
    """Campos para registrar 1 o 2 respaldos. Devuelve la lista de respaldos completos."""
    opciones = [t["id"] for t in bc.fuentes_json["tecnicas"]] + list(bc.metodologicas)
    out = []
    for n in (1, 2):
        st.markdown(f"**Respaldo {n}**" + ("" if n == 1 and obligatorio else " · opcional"))
        r1, r2 = st.columns([3, 1])
        fuente = r1.selectbox("Fuente", ["—"] + opciones, key=f"{prefijo}_f{n}",
                              format_func=lambda x: x if x == "—" else f"{x} · {nombre_fuente(x)}")
        respalda = r2.selectbox("Respalda", RESPALDA, key=f"{prefijo}_r{n}", format_func=lambda x: ETIQ_RESPALDA[x])
        r3, r4 = st.columns([1, 2])
        seccion_ = r3.text_input("Sección o página", key=f"{prefijo}_s{n}")
        evidencia = r4.text_input("Fragmento literal de la fuente", key=f"{prefijo}_e{n}")
        nota_ = st.text_input("Nota: qué demuestra para este caso", key=f"{prefijo}_n{n}")
        if fuente != "—":
            out.append({"fuente": fuente, "respalda": respalda, "seccion": seccion_.strip(),
                        "evidencia": evidencia.strip(), "nota": nota_.strip()})
    return out


with tab_admin:
    if not ss.admin:
        _, centro, _ = st.columns([1, 1.4, 1])
        with centro:
            icono_candado = ic("lock", 'style="font-size:30px;color:var(--primary);vertical-align:0"')
            h(f'<div style="text-align:center;margin:2rem 0 1rem"><div class="step" style="display:inline-flex;padding:14px;'
              f'border-radius:16px">{icono_candado}</div>'
              '<h3 style="margin:14px 0 4px">Acceso de administrador</h3>'
              '<p style="color:var(--muted);font-size:.9rem;margin:0">Necesario para agregar o validar casos.</p></div>')
            with st.form("login"):
                clave_login = st.text_input("Clave de administrador", type="password")
                entrar = st.form_submit_button("Ingresar", type="primary", icon=":material/login:", width="stretch")
            if entrar:
                if verificar_clave(clave_login):
                    ss.admin, ss.clave = True, clave_login
                    st.rerun()
                else:
                    st.error("Clave incorrecta.")
    else:
        h1, h2 = st.columns([5, 1])
        with h1:
            seccion("Administrar la base de conocimientos", "admin_panel_settings")
        with h2:
            st.write("")
            if st.button("Cerrar sesión", icon=":material/logout:", width="stretch"):
                ss.admin = False
                ss.pop("clave", None)
                st.rerun()
        if ss.get("admin_msg"):
            tipo, msg = ss.pop("admin_msg")
            getattr(st, tipo)(msg)

        tab_a_caso, tab_a_pend, tab_a_fuente, tab_a_sint = st.tabs(
            [":material/add_circle: Agregar caso", ":material/pending_actions: Validar pendientes",
             ":material/add_link: Agregar fuente", ":material/label: Agregar síntoma"])
        # ── Agregar caso ──
        with tab_a_caso:
            st.caption("Cada caso nuevo necesita su fuente de respaldo; sin ella queda «Pendiente» [1] p. 9. "
                       "Registre primero la fuente si aún no existe.")
            n1, n2 = st.columns(2)
            a_cat = n1.selectbox("Categoría", list(cats), format_func=lambda c: f"{c} · {cats[c]}", key="a_cat")
            a_subs = [c for c in bc.subcategoria_de if c.startswith(a_cat + ".")]
            a_sub = n2.selectbox("Subcategoría", a_subs, format_func=lambda c: f"{c} · {bc.subcategoria_de[c]}", key="a_sub")
            with st.form("nuevo_caso", clear_on_submit=False):
                d1, d2, d3 = st.columns(3)
                a_disp = d1.selectbox("Dispositivo", DISPOSITIVOS)
                a_so = d2.selectbox("Sistema operativo", SISTEMAS)
                a_con = d3.selectbox("Conexión", CONEXIONES)
                d4, d5, d6 = st.columns(3)
                a_tipo = d4.selectbox("Tipo de caso", ["Incidente", "Problema", "Requerimiento"])
                a_ubi = d5.selectbox("Ubicación", UBICACIONES)
                a_prio = d6.selectbox("Prioridad", ["Alta", "Media", "Baja"], index=1)
                a_sint = st.multiselect("Síntomas (de 1 a 3, al menos uno de falla)", list(bc.sintoma_nombre), max_selections=3, placeholder="Escriba para buscar un síntoma",
                                        format_func=lambda c: f"{bc.sintoma_nombre[c]} ({c}) · {bc.sintoma_grupo[c]}"
                                        + (" · dato adicional" if bc.sintoma_tipo.get(c) == "contexto" else ""))
                a_efecto = st.text_input("Efecto percibido por el usuario")
                a_obj = st.text_input("Objeto del fallo (componente)")
                a_causa = st.text_input("Causa")
                a_sol = st.text_area("Solución aplicada")
                d7, d8, d9 = st.columns(3)
                a_tiempo = d7.number_input("Tiempo de resolución (min)", min_value=1, value=10)
                a_nivel = d8.selectbox("Nivel de resolución", ["1.er nivel", "2.º nivel"])
                a_res = d9.selectbox("Resultado", ["Resuelto", "Resuelto parcialmente"])
                ap1, ap2 = st.columns(2)
                a_conap = ap1.multiselect("La solución sirve con conexión", CONEXIONES, default=CONEXIONES, placeholder="Elija una o más")
                a_disap = ap2.multiselect("La solución sirve en", DISPOSITIVOS, default=DISPOSITIVOS, placeholder="Elija una o más")
                a_soap = st.multiselect("La solución sirve en el sistema operativo", ["Windows", "Ubuntu"], default=["Windows", "Ubuntu"], placeholder="Elija uno o más",
                                        help="Marque solo Windows si la solución usa herramientas propias de Windows "
                                             "(Administrador de tareas, Configuración, Outlook…), o solo Ubuntu si usa apt, nmcli, etc.")
                st.divider()
                resp = editor_respaldo("ac")
                parcial = st.checkbox("La fuente respalda el caso solo en parte (estado «Validado parcialmente»)")
                guardar = st.form_submit_button("Guardar caso", type="primary", icon=":material/save:")
            if guardar:
                datos = dict(codigo_cat=a_sub, dispositivo=a_disp, so=a_so, conexion=a_con, sintomas=a_sint,
                             tipo_caso=a_tipo, ubicacion=a_ubi, prioridad=a_prio, efecto=a_efecto.strip(),
                             objeto_fallo=a_obj.strip(), causa=a_causa.strip(), solucion=a_sol.strip(),
                             tiempo_min=a_tiempo, nivel=a_nivel, resultado=a_res, so_aplicable=a_soap,
                             conexion_aplicable=a_conap, dispositivo_aplicable=a_disap)
                try:
                    msg = agregar_caso(motor, datos, resp, ss.clave,
                                       estado="Validado parcialmente" if parcial else "Validado")
                    actualizar_uso_fuentes(bc)
                    ss.admin_msg = ("success", msg + ("" if resp else " Agregue su fuente en «Validar pendientes»."))
                    recargar()
                    st.rerun()
                except (ValueError, PermissionError) as e:
                    st.error(str(e))

        # ── Validar pendientes ──
        with tab_a_pend:
            pend = bc.casos_pendientes
            if not pend:
                nota("No hay casos pendientes: todos los casos tienen respaldo documental.", "ok")
            else:
                st.caption("Casos retenidos desde tickets o agregados sin fuente. No se usan para recomendar hasta tener respaldo.")
                sel = st.selectbox("Caso pendiente", [c.id for c in pend],
                                   format_func=lambda i: f"{i} · {bc.caso(i).subcategoria} · {bc.caso(i).causa}")
                c = bc.caso(sel)
                h(f'<div class="card" style="margin-bottom:12px;font-size:.9rem;line-height:1.7">'
                  f'<b>Síntomas:</b> {esc("; ".join(bc.sintoma_nombre.get(s, s) for s in sorted(c.registrados)))}<br>'
                  f'<b>Causa:</b> {esc(c.causa)}<br><b>Solución:</b> {esc(c.solucion)}<br><b>Nivel:</b> {esc(c.nivel)}</div>')
                with st.form("validar_pend"):
                    resp_p = editor_respaldo("vp")
                    parcial_p = st.checkbox("Respaldo parcial")
                    b1, b2 = st.columns(2)
                    ok = b1.form_submit_button("Validar caso", type="primary", icon=":material/verified:")
                    rech = b2.form_submit_button("Eliminar caso (no se pudo respaldar)", icon=":material/delete:")
                if ok or rech:
                    try:
                        msg = (validar_caso(motor, sel, resp_p, ss.clave,
                                            "Validado parcialmente" if parcial_p else "Validado")
                               if ok else rechazar_caso(motor, sel, ss.clave))
                        actualizar_uso_fuentes(bc)
                        ss.admin_msg = ("success", msg)
                        recargar()
                        st.rerun()
                    except (ValueError, PermissionError) as e:
                        st.error(str(e))

        # ── Agregar fuente ──
        with tab_a_fuente:
            st.caption("Solo fuentes confiables y accesibles: documentación oficial, organismos (NIST, CISA, INCIBE) o "
                       "artículos académicos. Compruebe antes que la página contiene el respaldo.")
            with st.form("nueva_fuente", clear_on_submit=True):
                f_tit = st.text_input("Título de la página o documento")
                g1, g2, g3 = st.columns(3)
                f_org = g1.text_input("Organización (p. ej. Microsoft)")
                f_anio = g2.text_input("Año", value="s. f.")
                f_idi = g3.selectbox("Idioma", ["es", "en"])
                f_url = st.text_input("URL")
                f_tipo = st.selectbox("Tipo", ["Documentación oficial", "Guía gubernamental", "Artículo académico"])
                okf = st.form_submit_button("Registrar fuente", type="primary", icon=":material/add_link:")
            if okf:
                try:
                    nid = agregar_fuente_tecnica(bc, dict(titulo=f_tit, organizacion=f_org, anio=f_anio, idioma=f_idi,
                                                          url=f_url, tipo=f_tipo), ss.clave)
                    ss.admin_msg = ("success", f"Fuente registrada como {nid}. Ya puede usarla como respaldo.")
                    recargar()
                    st.rerun()
                except (ValueError, PermissionError) as e:
                    st.error(str(e))

        # ── Agregar síntoma ──
        with tab_a_sint:
            st.caption("Amplíe el catálogo solo si ningún síntoma existente describe la falla [5].")
            with st.form("nuevo_sintoma", clear_on_submit=True):
                s_nom = st.text_input("Nombre del síntoma (frase corta, p. ej. «Pantalla congelada»)")
                s_gru = st.selectbox("Grupo", ["Red", "Hardware", "Software", "Cuentas"])
                s_tipo = st.radio("Tipo", ["falla", "contexto"], horizontal=True,
                                  format_func=lambda t: "Síntoma de falla" if t == "falla" else "Dato adicional (contexto)")
                oks = st.form_submit_button("Agregar síntoma", type="primary", icon=":material/label:")
            if oks:
                try:
                    cod = agregar_sintoma(bc, s_nom, s_gru, ss.clave, tipo=s_tipo)
                    ss.admin_msg = ("success", f"Síntoma agregado como {cod}.")
                    recargar()
                    st.rerun()
                except (ValueError, PermissionError) as e:
                    st.error(str(e))

# ═════════════════════════════════════════════════════════════════════════════
# 5. VALIDACIÓN
# ═════════════════════════════════════════════════════════════════════════════
with tab_valid:
    v1, v2 = st.columns([3.6, 1.2])
    with v1:
        seccion("Validación dejando un caso fuera", "model_training",
                desc="Cada ticket de la base se usa como ticket nuevo contra el resto · [6] Tabla 5 · [3]")
    with v2:
        st.write("")
        if st.button("Ejecutar validación", icon=":material/play_arrow:", width="stretch"):
            ss.loo = {et: validar_loo(motor, et) for et in ("causa", "subcategoria")}
    if ss.get("loo"):
        m = ss.loo["causa"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tickets evaluados", m["casos"])
        c2.metric("Exactitud (top-1)", f"{m['exactitud_top1']:.1%}")
        c3.metric("Acierto en los 3 primeros", f"{m['acierto_top3']:.1%}")
        c4.metric("Similitud media", f"{m['similitud_media']:.2f}")
        with st.expander("Cómo leer estos resultados", icon=":material/info:"):
            st.markdown("La respuesta es correcta si el caso recuperado tiene **el mismo diagnóstico** (causa) que el ticket "
                        "dejado fuera. Cada falla tiene al menos dos tickets en la base (el original y su repetición en otro "
                        f"equipo). La subcategoría se acierta en {ss.loo['subcategoria']['exactitud_top1']:.1%} de los casos.")
            if m["fallos_top1"]:
                st.markdown("Fallos en el 1.er lugar (el ticket se confunde con otra falla de **síntomas idénticos**, "
                            "que el ticket no puede distinguir; la causa correcta queda entre los 3 primeros):")
                st.caption(" · ".join(f"{a} → {b}" for a, b in m["fallos_top1"]))

    v1, v2 = st.columns([3.6, 1.2])
    with v1:
        seccion("Casos de prueba", "fact_check",
                desc=f"Tickets simulados que no están en la base, con la respuesta esperada definida antes de ejecutar el sistema.")
    with v2:
        st.write("")
        if st.button("Ejecutar pruebas", icon=":material/play_arrow:", width="stretch"):
            ss.pruebas = evaluar_casos_prueba(motor)
    if ss.get("pruebas"):
        ev = ss.pruebas
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Casos de prueba", ev["casos"])
        c2.metric("Exactitud", f"{ev['exactitud']:.1%}")
        c3.metric("Acierto en los 3 primeros", f"{ev['acierto_top3']:.1%}")
        c4.metric("Similitud media", f"{ev['similitud_media']:.2f}")
        h('<div class="m" style="margin:2px 0 10px">' + " · ".join(
            f"<b>{esc(t.capitalize())}</b>: {d['aciertos']}/{d['total']}" for t, d in ev["por_tipo"].items()) + "</div>")
        N_ = bc.sintoma_nombre
        st.dataframe([{"ID": f["id"], "Tipo": f["tipo"], "Coincide": "Sí" if f["coincide"] else "No",
                       "Esperado": f["esperado"] + (f" ({', '.join(f['casos_esperados'][:2])})" if f["casos_esperados"] else ""),
                       "Sistema": f["sistema"] + (f" ({con_original(f['caso_sistema'])})" if f["caso_sistema"] != "—" else ""),
                       "Síntomas": "; ".join(N_.get(x, x) for x in f["ticket"]["sintomas"]),
                       "Ticket": f"{bc.subcategoria_de.get(f['ticket']['codigo_cat'], '')} · {f['ticket']['dispositivo']} · "
                                 f"{f['ticket']['so']} · {f['ticket']['conexion']}"} for f in ev["filas"]],
                     hide_index=True, width="stretch", height=320)
        with st.expander("Criterios y análisis de fallos", icon=":material/info:"):
            st.markdown("- **Proponer**: correcto si la causa propuesta es una de las esperadas.\n"
                        "- **Preguntar**: correcto si el sistema pide más datos y una causa esperada está entre sus 3 casos.\n"
                        "- **No proponer**: correcto si no propone solución (ticket contradictorio, fallas mezcladas o fuera de alcance).\n\n"
                        "La respuesta esperada se definió con la fuente técnica de la falla (no hay experto), así que puede "
                        "tener el sesgo del equipo; el archivo es `validacion/casos_prueba.json`.")
            for f in ev["filas"]:
                if not f["coincide"]:
                    st.markdown(f"**{f['id']}** — esperado «{f['esperado']}», el sistema respondió «{f['sistema']}» "
                                f"({f['caso_sistema']}). {esc(f['justificacion'])}")

    v1, v2 = st.columns([3.6, 1.2])
    with v1:
        seccion("Análisis de sensibilidad", "tune",
                desc="Cómo cambia el resultado con otros valores, como [7] Sec. 3.5 y [6] Tabla 5.")
    with v2:
        st.write("")
        if st.button("Ejecutar análisis", icon=":material/play_arrow:", width="stretch"):
            ss.sens = analisis_sensibilidad(motor)
    if ss.get("sens"):
        s = ss.sens
        cA, cB = st.columns(2)
        with cA:
            st.markdown("**Peso de los síntomas**")
            st.dataframe([{"Peso síntomas": f"{f['peso_sintomas']:.1f}" + ("  · actual" if f["actual"] else ""),
                           "Top-1 diagnóstico": f"{f['top1_causa']:.1%}",
                           "Top-3": f"{f['top3_causa']:.1%}",
                           "Robustez": f"{f['robustez']:.1%}"} for f in s["pesos"]],
                         hide_index=True, width="stretch")
            st.caption(bc.atributos["sintomas"].get("justificacion_valor", ""))
        with cB:
            st.markdown("**Umbral mínimo de similitud**")
            st.dataframe([{"Umbral": f"{f['umbral']:.2f}" + ("  · actual" if f["actual"] else ""),
                           "Exactitud (casos de prueba)": f"{f['exactitud']:.1%}",
                           "Propone cuando debe": f"{f['propone']:.1%}"} for f in s["umbral"]],
                         hide_index=True, width="stretch")
            st.caption(bc.parametros["umbral_minimo"].get("justificacion_valor", ""))

    v1, v2 = st.columns([3.6, 1.2])
    with v1:
        seccion("Auditoría de coherencia", "rule",
                desc="Prueba todas las combinaciones de 1 y 2 síntomas en 8 equipos y busca propuestas incoherentes.")
    with v2:
        st.write("")
        if st.button("Ejecutar auditoría", icon=":material/play_arrow:", width="stretch"):
            ss.audit = auditar_coherencia(motor)
    if ss.get("audit"):
        a_ = ss.audit
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Consultas probadas", a_["consultas"])
        k2.metric("Propone solución", a_["propone"])
        k3.metric("Pide más datos", a_["pregunta"])
        k4.metric("No propone (avisa o escala)", a_["escala"])
        if a_["problemas"]:
            nota(f"<b>{len(a_['problemas'])} problema(s) de coherencia</b>", "bad")
            for x in a_["problemas"]:
                st.markdown(f"- {x}")
        else:
            nota("<b>0 problemas de coherencia.</b> Todas las propuestas aplican al equipo del ticket, no contradicen sus "
                 "síntomas y explican todos los síntomas de falla marcados; cada caso recupera su propio diagnóstico.", "ok", "verified")

    seccion("Verificación de la base", "inventory", desc="Respaldos, fuentes, duplicados y catálogo · [11] · [9] Sec. 5")
    clases = {"OK": ("ok", "check_circle"), "AVISO": ("warn", "error"), "ERROR": ("bad", "cancel")}
    h('<div class="card" style="padding:6px 20px">' + "".join(
        f'<div class="chk {clases[nv][0]}">{ic(clases[nv][1])}<span>{esc(msg)}</span></div>'
        for nv, msg in verificar_base(bc)) + "</div>")

# ═════════════════════════════════════════════════════════════════════════════
# 6. FUENTES Y JUSTIFICACIÓN
# ═════════════════════════════════════════════════════════════════════════════
with tab_fuentes:
    seccion("Por qué el sistema decide así", "gavel", desc="Respuestas para la sustentación, con su fuente y ubicación.")
    P = bc.parametros
    A = bc.atributos
    R = bc.reglas
    faq = [
        ("¿Por qué el sistema recomienda ese caso y no otro?",
         f"Calcula la similitud global como la suma ponderada de las similitudes de cada atributo y ordena los casos "
         f"de mayor a menor (k vecinos más cercanos). {bc.similitud_json['fuente_formula']}. Recuperación k-NN: {P['k']['fuente']}."),
        ("¿Cómo saben que la solución es correcta si no hubo un experto?",
         "Cada caso tiene en «validacion.respaldo» una fuente técnica oficial (código T), la sección y un fragmento "
         "literal que respalda su causa y su solución; se ve en la pestaña Base de casos. Solo los casos validados se "
         "usan para recomendar: [1] p. 9 (se retiene la solución «confirmada o validada»); [8] Sec. 7 (revisión). "
         f"Hoy hay {sum(c.estado == 'Validado' for c in bc.casos)} casos con causa y solución respaldadas y "
         f"{sum(c.estado == 'Validado parcialmente' for c in bc.casos)} con respaldo parcial; en estos la limitación "
         "está escrita en el caso. Un segundo revisor volvió a abrir cada página y comprobó que los fragmentos citados están en ella."),
        (f"¿Por qué los síntomas pesan más ({bc.pesos['sintomas']:.1f})?".replace(".", ","),
         f"{A['sintomas']['justificacion_valor']} Que los pesos se asignen con conocimiento del dominio: {bc.similitud_json['fuente_pesos']}"),
        ("¿Por qué Jaccard para comparar síntomas?",
         f"Porque los síntomas son un conjunto de etiquetas de un vocabulario cerrado, y Jaccard mide la proporción en común: {A['sintomas']['fuente_metodo']}."),
        ("¿Por qué comparar la subcategoría con un árbol?",
         f"Una falla de la misma categoría padre se parece más que una de otra categoría: {A['subcategoria']['fuente_metodo']}; tabla de categorías con código: [4] p. 86."),
        ("¿Por qué se muestran 3 casos?",
         f"{P['k']['justificacion_valor']} Método: {P['k']['fuente']}."),
        (f"¿Por qué no propone solución si la similitud es menor a {bc.umbral_minimo:.0%}?",
         f"{P['umbral_minimo']['uso']} Fuente: {P['umbral_minimo']['fuente']}. El valor se contrastó con el análisis de sensibilidad (pestaña Validación)."),
        ("¿Por qué cambia los comandos cuando el equipo es Ubuntu?",
         "Regla R1 de adaptación por sustitución ([9] Sec. 4; [8] Sec. 6). Cada equivalencia tiene su fuente oficial: "
         + "; ".join(f"{s['windows']} → {s['ubuntu']} ({s['fuente_windows']}, {s['fuente_ubuntu']})" for s in R["R1"]["sustituciones_windows_a_ubuntu"]) + "."),
        ("¿Por qué manda a 2.º nivel?",
         f"R4: {R['R4']['si'].lower()} → {R['R4']['entonces'].lower()} ({'; '.join(R['R4']['fuentes'])}). "
         f"R5: {R['R5']['si'].lower()} → {R['R5']['entonces'].lower()} ({'; '.join(R['R5']['fuentes'])})."),
        ("¿Qué pasa si dos casos empatan?",
         "Se desempata en este orden: " + "; ".join(f"{d['orden']}) {d['criterio']} ({d['fuente']})" for d in P["desempates"]) + "."),
        ("¿Cómo aprende el sistema?",
         f"{P['umbral_retencion']['uso']} Fuente: {P['umbral_retencion']['fuente']}. Además exige confirmación del técnico, "
         f"conformidad del usuario y la clave de administrador ({P['condicion_retener']['fuente']}); el caso nuevo queda «Pendiente» hasta tener respaldo."),
        ("¿Por qué marca algunos síntomas como «inferidos»?",
         f"{bc.catalogo_json['inferencia']['descripcion']} Fuente: {bc.catalogo_json['inferencia']['fuente']}: "
         f"«{bc.catalogo_json['inferencia']['evidencia']}». Criterio: {bc.catalogo_json['inferencia']['criterio']}"),
        ("¿Qué hace si ningún caso explica todos los síntomas?",
         f"{P['fallas_mezcladas']['valor']} {P['fallas_mezcladas']['uso']} Fuente: {P['fallas_mezcladas']['fuente']}."),
        ("¿Cómo se validó el sistema?",
         "Como pide la ficha del proyecto P9: validación dejando un caso fuera con exactitud (top-1) y acierto en los 3 "
         "primeros ([6] Tabla 5; [3]), sobre todos los tickets de la base, donde cada falla tiene al menos dos tickets. "
         f"Además, {len(_leer_pruebas())} casos de prueba simulados (típicos, difíciles y límite) que no están en la base, "
         "con la respuesta esperada definida antes de ejecutar el sistema; la verificación de la base (duplicados y "
         "contradicciones, [11]); el análisis de sensibilidad de pesos y umbral ([7] Sec. 3.5) y la auditoría de coherencia."),
        ("¿Por qué una lista cerrada de síntomas y no texto libre?",
         f"{bc.catalogo_json['descripcion']} Fuente: {bc.catalogo_json['fuente']}. Es una limitación declarada del prototipo."),
        ("¿Por qué a veces el sistema pregunta en vez de dar una solución?",
         f"{P['cobertura_minima']['uso']} {P['margen_empate']['uso']} Fuentes: {P['cobertura_minima']['fuente']}."),
        ("¿Por qué no propone la solución de un caso de otra subcategoría?",
         f"{P['busqueda_por_niveles']['uso']} {P['umbral_sintomas_otra_subcategoria']['uso']} Fuentes: "
         f"{P['busqueda_por_niveles']['fuente']}; {P['umbral_sintomas_otra_subcategoria']['fuente']}."),
        ("¿Por qué no propone en Ubuntu una solución de Windows (o al revés)?",
         f"{P['so_aplicable']['uso']} Fuente: {P['so_aplicable']['fuente']}."),
        ("¿Por qué no propone «acercarse al punto de acceso» si la conexión es cableada?",
         f"{P['conexion_y_dispositivo_aplicable']['valor']} {P['conexion_y_dispositivo_aplicable']['uso']} "
         f"Fuente: {P['conexion_y_dispositivo_aplicable']['fuente']}."),
        ("¿Qué es un síntoma «dato adicional»?",
         f"{P['sintomas_de_contexto']['valor']} Fuente: {P['sintomas_de_contexto']['fuente']}. Además, hay síntomas "
         "excluyentes (p. ej. cable USB frente a Bluetooth): un caso que marca uno no se recupera si el ticket marcó otro."),
        ("¿Por qué razonamiento basado en casos y no solo reglas?",
         "El RBC resuelve problemas nuevos reutilizando casos resueltos similares [8] Sec. 1; sus casos se agregan uno a uno "
         "sin reescribir reglas, y cada sugerencia se explica mostrando casos reales [9] Sec. 3.3.5. En mesas de ayuda ya se "
         "aplicó con buenos resultados: [7] y [1]."),
    ]
    for pregunta, respuesta in faq:
        with st.expander(pregunta, icon=":material/chevron_right:"):
            st.markdown(respuesta)
            leyenda_fuentes([respuesta])

    seccion("Matriz de trazabilidad", "account_tree", desc="Cada elemento del sistema con la fuente que lo justifica.")
    filas = [{"Elemento": "Fórmula de similitud global", "Valor": bc.similitud_json["formula_global"],
              "Fuente del método": bc.similitud_json["fuente_formula"], "Justificación del valor": "—"}]
    for a in bc.similitud_json["atributos"]:
        filas.append({"Elemento": f"Similitud de {a['nombre'].lower()}", "Valor": f"{a['similitud_local']} · peso {a['peso']}",
                      "Fuente del método": a["fuente_metodo"], "Justificación del valor": a["justificacion_valor"]})
    for clave_p in ("k", "umbral_minimo", "umbral_retencion", "cobertura_minima", "inferencia_sintomas",
                    "contexto_no_confirmado", "fallas_mezcladas"):
        x = P[clave_p]
        filas.append({"Elemento": clave_p.replace("_", " ").capitalize(), "Valor": str(x["valor"]),
                      "Fuente del método": x["fuente"], "Justificación del valor": x.get("justificacion_valor", "—")})
    for d in P["desempates"]:
        filas.append({"Elemento": f"Desempate {d['orden']}", "Valor": d["criterio"], "Fuente del método": d["fuente"],
                      "Justificación del valor": "—"})
    for r in bc.reglas_json["reglas"]:
        filas.append({"Elemento": f"Regla {r['id']} ({r['tipo'].lower()})", "Valor": f"SI {r['si']} ENTONCES {r['entonces']}",
                      "Fuente del método": "; ".join(r["fuentes"]), "Justificación del valor": "—"})
    for e in bc.estructura["atributos"]:
        filas.append({"Elemento": f"Campo «{e['campo']}»", "Valor": e["tipo"], "Fuente del método": e["fuente"],
                      "Justificación del valor": "Entra en la similitud" if e["similitud"] else "No entra en la similitud"})
    filas.append({"Elemento": "Catálogo de síntomas", "Valor": f"{len(bc.sintoma_nombre)} síntomas",
                  "Fuente del método": bc.catalogo_json["fuente"], "Justificación del valor": "—"})
    filas.append({"Elemento": "Contenido de cada caso", "Valor": f"{len(bc.casos)} casos",
                  "Fuente del método": "Fuentes técnicas T (ver tabla siguiente y Base de casos)",
                  "Justificación del valor": "Fragmento literal por caso"})
    st.dataframe(filas, hide_index=True, width="stretch")

    seccion(f"Fuentes metodológicas · {len(bc.metodologicas)}", "school")
    st.dataframe([{"N.º": f"[{f['id']}]", "Referencia (IEEE)": f["ieee"], "Qué justifica": f["justifica"],
                   "Archivo": f.get("cita_archivo", ""), "Enlace": f.get("url", "")}
                  for f in bc.fuentes_json["metodologicas"]], hide_index=True, width="stretch",
                 column_config={"Enlace": st.column_config.LinkColumn("Enlace")})
    st.caption(next((f["nota_paginas"] for f in bc.fuentes_json["metodologicas"] if f.get("nota_paginas")), ""))

    seccion(f"Fuentes técnicas · {len(bc.tecnicas)}", "link")
    st.dataframe([{"Código": t["id"], "Organización": t["organizacion"], "Título": t["titulo"], "Año": t["anio"],
                   "Idioma": t["idioma"], "Casos que respalda": ", ".join(t.get("casos", [])),
                   "Reglas": ", ".join(t.get("reglas", [])), "Enlace": t["url"]}
                  for t in bc.fuentes_json["tecnicas"]], hide_index=True, width="stretch",
                 column_config={"Enlace": st.column_config.LinkColumn("Enlace")})
