import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests
import json
import os

# CONFIGURAZIONE PAGINA
st.set_page_config(page_title="Valigia Smart — Famiglia Giorgio", page_icon="🧳", layout="wide")

# Stile: titoli in Fraunces, coerenti con le altre app di famiglia
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');
h1, h2, h3 { font-family: 'Fraunces', Georgia, serif !important; letter-spacing: -0.01em; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_SALVATAGGIO = os.path.join(BASE_DIR, "stato_valigia.json")
STATI_OPZIONI = ["⚪ Da fare", "🟠 In parte", "🟡 Ultimo min", "🔴 Zero", "🟢 FATTO"]

# --- 0. GESTIONE SALVATAGGIO STATO ---
def carica_salvataggio():
    if os.path.exists(FILE_SALVATAGGIO):
        try:
            with open(FILE_SALVATAGGIO, "r") as f:
                return json.load(f)
        except Exception:
            return {"impostazioni": {}, "stati": {}, "racc": {}}
    return {"impostazioni": {}, "stati": {}, "racc": {}}

# Carichiamo i dati salvati (se esistono) solo al primo avvio della sessione
if 'dati_salvati' not in st.session_state:
    st.session_state.dati_salvati = carica_salvataggio()
    st.session_state.stati_globali = st.session_state.dati_salvati.get("stati", {})

# Ripristino da backup caricato (applicato PRIMA di creare i widget)
if 'pending_restore' in st.session_state:
    dati = st.session_state.pop('pending_restore')
    st.session_state.stati_globali = dati.get("stati", {})
    imp = dati.get("impostazioni", {})
    if imp:
        st.session_state.citta = imp.get("citta", "Alassio")
        st.session_state.tipo_v = imp.get("tipo_v", "Mare")
        st.session_state.alloggio = imp.get("alloggio", "Hotel")
        st.session_state.cane_presente = imp.get("cane_presente", True)
        try:
            st.session_state.d_inizio = datetime.strptime(imp.get("d_inizio"), "%Y-%m-%d").date()
            st.session_state.d_fine = datetime.strptime(imp.get("d_fine"), "%Y-%m-%d").date()
        except Exception:
            pass
    for k, v in dati.get("racc", {}).items():
        st.session_state[k] = v
    st.toast("📂 Backup ripristinato!", icon="✅")

def dati_correnti():
    return {
        "impostazioni": {
            "citta": st.session_state.citta,
            "d_inizio": str(st.session_state.d_inizio),
            "d_fine": str(st.session_state.d_fine),
            "tipo_v": st.session_state.tipo_v,
            "alloggio": st.session_state.alloggio,
            "cane_presente": st.session_state.cane_presente
        },
        "stati": st.session_state.stati_globali,
        "racc": {f"r_{i}": bool(st.session_state.get(f"r_{i}", False)) for i in range(9)}
    }

def salva_tutto():
    with open(FILE_SALVATAGGIO, "w") as f:
        json.dump(dati_correnti(), f)
    st.toast("💾 Salvato sul server. Per sicurezza scarica anche il backup!", icon="✅")

def reset_tutto():
    if os.path.exists(FILE_SALVATAGGIO):
        os.remove(FILE_SALVATAGGIO)
    st.session_state.clear()

# --- RECUPERO IMPOSTAZIONI SALVATE ---
impostazioni_salvate = st.session_state.dati_salvati.get("impostazioni", {})
racc_salvate = st.session_state.dati_salvati.get("racc", {})
citta_default = impostazioni_salvate.get("citta", "Alassio")
tipo_v_default = impostazioni_salvate.get("tipo_v", "Mare")
alloggio_default = impostazioni_salvate.get("alloggio", "Hotel")
cane_default = impostazioni_salvate.get("cane_presente", True)

try:
    d_inizio_default = datetime.strptime(impostazioni_salvate.get("d_inizio", str(date.today())), "%Y-%m-%d").date()
    d_fine_default = datetime.strptime(impostazioni_salvate.get("d_fine", str(date.today())), "%Y-%m-%d").date()
except Exception:
    d_inizio_default = date.today()
    d_fine_default = date.today()


# 1. FUNZIONE PER GENERARE LINK AERONAUTICA MILITARE
def get_meteoam_link(citta):
    citta_url = citta.lower().replace(" ", "-")
    return f"https://www.meteoam.it/it/meteo-citta/{citta_url}"

# 2. FUNZIONE METEO AUTOMATICO (cache 30 min per non martellare l'API)
@st.cache_data(ttl=1800, show_spinner=False)
def get_weather_forecast(citta):
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={citta}&count=1&language=it&format=json"
        geo_res = requests.get(geo_url, timeout=6).json()
        if not geo_res.get('results'):
            return None
        lat, lon = geo_res['results'][0]['latitude'], geo_res['results'][0]['longitude']
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,precipitation_probability_max,wind_speed_10m_max&timezone=auto"
        w_res = requests.get(weather_url, timeout=6).json()
        return w_res['daily']
    except Exception:
        return None

# 3. CARICAMENTO DATI
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(os.path.join(BASE_DIR, "Per viaggiare.csv"), sep=";")
        df.columns = df.columns.str.strip()
        if 'Oggetto' not in df.columns and 's' in df.columns:
            df = df.rename(columns={'s': 'Oggetto'})
        # le righe senza Proprietario sono note/legenda in fondo al CSV, non oggetti
        df = df.dropna(subset=['Proprietario'])
        df['Oggetto'] = df['Oggetto'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Errore: Carica 'Per viaggiare.csv' su GitHub. Dettaglio: {e}")
        return None

df_master = load_data()

if df_master is not None:
    # --- SIDEBAR: SETUP VIAGGIO ---
    st.sidebar.header("📋 Setup Viaggio")

    st.sidebar.text_input("Destinazione", value=citta_default, key="citta")
    st.sidebar.date_input("Data Arrivo", value=d_inizio_default, key="d_inizio")
    st.sidebar.date_input("Data Partenza", value=d_fine_default, key="d_fine")

    giorni = (st.session_state.d_fine - st.session_state.d_inizio).days
    if giorni <= 0:
        giorni = 1

    st.sidebar.divider()
    st.sidebar.selectbox("Contesto", ["Mare", "Montagna", "Città"], index=["Mare", "Montagna", "Città"].index(tipo_v_default), key="tipo_v")
    st.sidebar.radio("Soggiorno", ["Hotel", "Appartamento"], index=["Hotel", "Appartamento"].index(alloggio_default), key="alloggio")
    st.sidebar.toggle("Il cane viene con noi?", value=cane_default, key="cane_presente")

    st.sidebar.divider()

    # SALVA / BACKUP / RESET
    st.sidebar.button("💾 SALVA PROGRESSO", on_click=salva_tutto, type="primary", use_container_width=True)
    st.sidebar.caption("⚠️ Il salvataggio sul server può andare perso quando l'app si riavvia: scarica il backup qui sotto per non perdere nulla.")
    st.sidebar.download_button(
        "⬇️ Scarica backup (file)",
        data=json.dumps(dati_correnti(), ensure_ascii=False, indent=1),
        file_name=f"valigia-{st.session_state.citta}-{date.today()}.json",
        mime="application/json",
        use_container_width=True
    )
    up = st.sidebar.file_uploader("📂 Ripristina da backup", type="json", key="uploader_backup")
    if up is not None:
        firma = f"{up.name}-{up.size}"
        if st.session_state.get('ultimo_backup') != firma:
            try:
                st.session_state.pending_restore = json.load(up)
                st.session_state.ultimo_backup = firma
                st.rerun()
            except Exception:
                st.sidebar.error("File di backup non valido.")
    st.sidebar.button("🗑️ RESET VALIGIA", on_click=reset_tutto, use_container_width=True)

    st.sidebar.divider()

    # --- METEO ---
    st.sidebar.subheader("🌦️ Meteo")
    url_am = get_meteoam_link(st.session_state.citta)
    st.sidebar.link_button("Apri Meteo Aeronautica ↗️", url_am)

    meteo_auto = get_weather_forecast(st.session_state.citta)
    p_sugg = max(meteo_auto['precipitation_probability_max']) > 30 if meteo_auto else False
    v_sugg = "Debole"
    if meteo_auto:
        v_max = max(meteo_auto['wind_speed_10m_max'])
        v_sugg = "Forte" if v_max > 30 else ("Medio" if v_max > 15 else "Debole")
        t3 = meteo_auto['temperature_2m_max'][:3]
        p3 = meteo_auto['precipitation_probability_max'][:3]
        st.sidebar.caption(
            f"Previsioni {st.session_state.citta} (prossimi 3 giorni): "
            f"max {t3[0]:.0f}° / {t3[1]:.0f}° / {t3[2]:.0f}° · pioggia fino al {max(p3):.0f}%"
        )
    else:
        st.sidebar.caption("Previsioni automatiche non disponibili — consulta il sito sopra.")

    st.sidebar.caption("Conferma qui sotto i dati reali (da MeteoAM):")
    override_cielo = st.sidebar.multiselect("Cielo:", ["Sole", "Nuvole", "Pioggia"], default=["Pioggia"] if p_sugg else ["Sole"])
    override_vento = st.sidebar.select_slider("Vento:", options=["Debole", "Medio", "Forte"], value=v_sugg)
    pioggia_master = "Pioggia" in override_cielo

    # --- MOTORE DI CALCOLO DINAMICO ---
    def calcola_final(row, giorni, pioggia_on, vento_livello, cane_ok):
        ogg = str(row['Oggetto']).lower()
        prop = str(row['Proprietario']).lower()

        if not cane_ok and ("cane" in prop or "cane:" in ogg):
            return 0

        tipo_casa = str(row.get('Hotel / Appartamento / Entrambi', 'Entrambi')).strip()
        if st.session_state.alloggio == "Hotel" and tipo_casa == "Appartamento":
            return 0
        if st.session_state.alloggio == "Appartamento" and tipo_casa == "Hotel":
            return 0

        cont_row = str(row.get('Tipo viaggio / Contesto', 'Tutti'))
        if "Mare" in cont_row and st.session_state.tipo_v != "Mare":
            return 0
        if "Montagna" in cont_row and st.session_state.tipo_v != "Montagna":
            return 0

        if "mutande" in ogg or "calze" in ogg:
            return giorni + 1
        if "magliette maniche corte" in ogg:
            return giorni + 2 if ("ilaria" in prop or "emma" in prop) else giorni

        if ("k-way" in ogg or "ombrellino" in ogg) and not pioggia_on:
            return 0
        if "ombrellone" in ogg and vento_livello == "Forte":
            return 0

        try:
            val = row['Quantità']
            if pd.isnull(val) or val == "" or val == "-1":
                return 1
            return int(val)
        except Exception:
            return 1

    # --- INTERFACCIA PRINCIPALE ---
    st.title(f"🧳 Valigia Smart per {st.session_state.citta}")
    st.caption(f"📅 {st.session_state.d_inizio.strftime('%d/%m/%Y')} → {st.session_state.d_fine.strftime('%d/%m/%Y')} · {giorni} giorn{'o' if giorni == 1 else 'i'} · {st.session_state.tipo_v} · {st.session_state.alloggio}" + (" · 🐕 col cane" if st.session_state.cane_presente else ""))

    with st.expander("🚨 RACCOMANDAZIONI PRE-PARTENZA", expanded=True):
        racc = ["Chiudo finestre mansarda e taverna", "Spengo NAS", "Coprire piscina", "Frutta in frigo giù nel sacchetto umido", "LASCIA A CASA LE COSE INUTILI", "BUTTA IMMONDIZIA", "PULISCI CASA e baygon (no briciole)", "Partire con cell carichi", "Metti antifurti, togli programmazione"]
        cols_r = st.columns(3)
        for i, r in enumerate(racc):
            cols_r[i % 3].checkbox(r, value=bool(racc_salvate.get(f"r_{i}", False)), key=f"r_{i}")

    f_piano = st.multiselect("📍 Filtra per Piano:", sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)]), default=sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)]))

    df_master['Quantità_Calc'] = df_master.apply(lambda x: calcola_final(x, giorni, pioggia_master, override_vento, st.session_state.cane_presente), axis=1)

    nomi_p = ["Giorgio", "Olga", "Ilaria", "Emma", "Comune"]
    emoji_p = {"Giorgio": "🕺", "Olga": "💃", "Ilaria": "👧", "Emma": "👶", "Comune": "🏠"}

    # Costruisci prima tutte le liste per calcolare i progressi
    dfs = {}
    for nome_t in nomi_p:
        if nome_t == "Comune":
            mask = (df_master['Proprietario'] == 'Comune') | (df_master['Proprietario'].str.contains('Cane', na=False, case=False))
        else:
            # str.contains così "Ilaria / Emma" compare sia a Ilaria che a Emma
            mask = (df_master['Proprietario'].str.contains(nome_t, na=False, case=False)) | (df_master['Proprietario'] == 'Ciascuno')
        df_tab = df_master[mask & df_master['Posiz. piano'].astype(str).isin(f_piano)].copy()
        # Nascondi gli oggetti che il motore ha escluso (quantità 0: contesto, alloggio, cane, meteo)
        df_tab = df_tab[df_tab['Quantità_Calc'] > 0]
        df_tab['Stato'] = df_tab['Oggetto'].apply(lambda o: st.session_state.stati_globali.get(f"{nome_t}_{o}", "⚪ Da fare"))
        dfs[nome_t] = df_tab

    tot_oggetti = sum(len(d) for d in dfs.values())
    tot_fatti = sum(int((d['Stato'] == "🟢 FATTO").sum()) for d in dfs.values())

    c1, c2, c3 = st.columns(3)
    c1.metric("📦 Oggetti da preparare", tot_oggetti)
    c2.metric("✅ Fatti", tot_fatti)
    c3.metric("🎯 Avanzamento", f"{(tot_fatti / tot_oggetti * 100):.0f}%" if tot_oggetti else "—")
    st.progress(tot_fatti / tot_oggetti if tot_oggetti else 0.0)

    etichette = [f"{emoji_p[n]} {n} · {int((dfs[n]['Stato'] == '🟢 FATTO').sum())}/{len(dfs[n])}" for n in nomi_p]
    tabs = st.tabs(etichette)

    for i, tab in enumerate(tabs):
        with tab:
            nome_t = nomi_p[i]
            df_tab = dfs[nome_t]

            n_tot, n_fatti = len(df_tab), int((df_tab['Stato'] == "🟢 FATTO").sum())
            if n_tot == 0:
                st.info("Nessun oggetto per questa selezione di piani / contesto.")
                continue
            st.progress(n_fatti / n_tot, text=f"{n_fatti} su {n_tot} fatti")

            df_edited = st.data_editor(
                df_tab[['Stato', 'Oggetto', 'Quantità_Calc', 'Posiz. piano', 'Note']],
                column_config={
                    "Stato": st.column_config.SelectboxColumn("Stato", options=STATI_OPZIONI),
                    "Quantità_Calc": "Q.tà",
                    "Posiz. piano": "Piano",
                    "Oggetto": st.column_config.TextColumn("Oggetto", disabled=True)
                },
                hide_index=True,
                use_container_width=True,
                key=f"ed_{nome_t}"
            )

            # Aggiorna il dizionario globale in tempo reale con le modifiche fatte
            for index, row in df_edited.iterrows():
                chiave = f"{nome_t}_{row['Oggetto']}"
                st.session_state.stati_globali[chiave] = row['Stato']
