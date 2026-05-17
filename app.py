import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests
import json
import os

# CONFIGURAZIONE PAGINA
st.set_page_config(page_title="Valigia Smart v3.0 - Famiglia Giorgio", layout="wide")

FILE_SALVATAGGIO = "stato_valigia.json"

# --- 0. GESTIONE SALVATAGGIO STATO ---
def carica_salvataggio():
    if os.path.exists(FILE_SALVATAGGIO):
        try:
            with open(FILE_SALVATAGGIO, "r") as f:
                return json.load(f)
        except:
            return {"impostazioni": {}, "stati": {}}
    return {"impostazioni": {}, "stati": {}}

# Carichiamo i dati salvati (se esistono) solo al primo avvio della sessione
if 'dati_salvati' not in st.session_state:
    st.session_state.dati_salvati = carica_salvataggio()
    # Inizializziamo il dizionario che terrà in memoria le spunte in tempo reale
    st.session_state.stati_globali = st.session_state.dati_salvati.get("stati", {})

def salva_tutto():
    dati_da_salvare = {
        "impostazioni": {
            "citta": st.session_state.citta,
            "d_inizio": str(st.session_state.d_inizio),
            "d_fine": str(st.session_state.d_fine),
            "tipo_v": st.session_state.tipo_v,
            "alloggio": st.session_state.alloggio,
            "cane_presente": st.session_state.cane_presente
        },
        "stati": st.session_state.stati_globali
    }
    with open(FILE_SALVATAGGIO, "w") as f:
        json.dump(dati_da_salvare, f)
    st.toast("💾 Valigia salvata con successo! Puoi chiudere l'app.", icon="✅")

def reset_tutto():
    if os.path.exists(FILE_SALVATAGGIO):
        os.remove(FILE_SALVATAGGIO)
    st.session_state.clear()
    st.rerun()

# --- RECUPERO IMPOSTAZIONI SALVATE ---
impostazioni_salvate = st.session_state.dati_salvati.get("impostazioni", {})
citta_default = impostazioni_salvate.get("citta", "Alassio")
tipo_v_default = impostazioni_salvate.get("tipo_v", "Mare")
alloggio_default = impostazioni_salvate.get("alloggio", "Hotel")
cane_default = impostazioni_salvate.get("cane_presente", True)

# Gestione date salvate
try:
    d_inizio_default = datetime.strptime(impostazioni_salvate.get("d_inizio", str(date.today())), "%Y-%m-%d").date()
    d_fine_default = datetime.strptime(impostazioni_salvate.get("d_fine", str(date.today())), "%Y-%m-%d").date()
except:
    d_inizio_default = date.today()
    d_fine_default = date.today()


# 1. FUNZIONE PER GENERARE LINK AERONAUTICA MILITARE
def get_meteoam_link(citta):
    citta_url = citta.lower().replace(" ", "-")
    return f"https://www.meteoam.it/it/meteo-citta/{citta_url}"

# 2. FUNZIONE METEO AUTOMATICO
def get_weather_forecast(citta):
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={citta}&count=1&language=it&format=json"
        geo_res = requests.get(geo_url).json()
        if not geo_res.get('results'): return None
        lat, lon = geo_res['results'][0]['latitude'], geo_res['results'][0]['longitude']
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,precipitation_probability_max,wind_speed_10m_max&timezone=auto"
        w_res = requests.get(weather_url).json()
        return w_res['daily']
    except:
        return None

# 3. CARICAMENTO DATI
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("Per viaggiare.csv", sep=";")
        df.columns = df.columns.str.strip()
        if 'Oggetto' not in df.columns and 's' in df.columns:
            df = df.rename(columns={'s': 'Oggetto'})
        return df
    except Exception as e:
        st.error(f"Errore: Carica 'Per viaggiare.csv' su GitHub. Dettaglio: {e}")
        return None

df_master = load_data()

if df_master is not None:
    # --- SIDEBAR: SETUP VIAGGIO ---
    st.sidebar.header("📋 Setup Viaggio")
    
    # Widget collegati alla session_state per poterli salvare
    st.sidebar.text_input("Destinazione", value=citta_default, key="citta")
    st.sidebar.date_input("Data Arrivo", value=d_inizio_default, key="d_inizio")
    st.sidebar.date_input("Data Partenza", value=d_fine_default, key="d_fine")
    
    giorni = (st.session_state.d_fine - st.session_state.d_inizio).days
    if giorni <= 0: giorni = 1
    
    st.sidebar.divider()
    st.sidebar.selectbox("Contesto", ["Mare", "Montagna", "Città"], index=["Mare", "Montagna", "Città"].index(tipo_v_default), key="tipo_v")
    st.sidebar.radio("Soggiorno", ["Hotel", "Appartamento"], index=["Hotel", "Appartamento"].index(alloggio_default), key="alloggio")
    st.sidebar.toggle("Il cane viene con noi?", value=cane_default, key="cane_presente")
    
    st.sidebar.divider()
    
    # PULSANTI SALVA / RESET
    st.sidebar.button("💾 SALVA PROGRESSO", on_click=salva_tutto, type="primary", use_container_width=True)
    st.sidebar.button("🗑️ RESET VALIGIA", on_click=reset_tutto, use_container_width=True)
    
    st.sidebar.divider()
    
    # --- METEO UFFICIALE AERONAUTICA ---
    st.sidebar.subheader("🌦️ Meteo Ufficiale")
    url_am = get_meteoam_link(st.session_state.citta)
    st.sidebar.link_button("Apri Meteo Aeronautica ↗️", url_am)
    
    st.sidebar.caption("Consulta il sito sopra e imposta qui sotto i dati reali:")
    
    meteo_auto = get_weather_forecast(st.session_state.citta)
    p_sugg = max(meteo_auto['precipitation_probability_max']) > 30 if meteo_auto else False
    v_sugg = "Debole"
    if meteo_auto:
        v_max = max(meteo_auto['wind_speed_10m_max'])
        v_sugg = "Forte" if v_max > 30 else ("Medio" if v_max > 15 else "Debole")

    override_cielo = st.sidebar.multiselect("Cielo (da MeteoAM):", ["Sole", "Nuvole", "Pioggia"], default=["Pioggia"] if p_sugg else ["Sole"])
    override_vento = st.sidebar.select_slider("Vento (da MeteoAM):", options=["Debole", "Medio", "Forte"], value=v_sugg)
    pioggia_master = "Pioggia" in override_cielo

    # --- MOTORE DI CALCOLO DINAMICO ---
    def calcola_final(row, giorni, pioggia_on, vento_livello, cane_ok):
        ogg = str(row['Oggetto']).lower()
        prop = str(row['Proprietario']).lower()
        
        if not cane_ok and ("cane" in prop or "cane:" in ogg): return 0
        
        tipo_casa = str(row.get('Hotel / Appartamento / Entrambi', 'Entrambi')).strip()
        if st.session_state.alloggio == "Hotel" and tipo_casa == "Appartamento": return 0
        if st.session_state.alloggio == "Appartamento" and tipo_casa == "Hotel": return 0
        
        cont_row = str(row.get('Tipo viaggio / Contesto', 'Tutti'))
        if "Mare" in cont_row and st.session_state.tipo_v != "Mare": return 0
        if "Montagna" in cont_row and st.session_state.tipo_v != "Montagna": return 0
        
        if "mutande" in ogg or "calze" in ogg: return giorni + 1
        if "magliette maniche corte" in ogg:
            return giorni + 2 if ("ilaria" in prop or "emma" in prop) else giorni
        
        if ("k-way" in ogg or "ombrellino" in ogg) and not pioggia_on: return 0
        if "ombrellone" in ogg and vento_livello == "Forte": return 0

        try:
            val = row['Quantità']
            if pd.isnull(val) or val == "" or val == "-1": return 1
            return int(val)
        except: return 1

    # --- INTERFACCIA PRINCIPALE ---
    st.title(f"🧳 Valigia Smart per {st.session_state.citta}")
    
    with st.expander("🚨 RACCOMANDAZIONI PRE-PARTENZA", expanded=True):
        racc = ["Chiudo finestre mansarda e taverna", "Spengo NAS", "Coprire piscina", "Frutta in frigo giù nel sacchetto umido", "LASCIA A CASA LE COSE INUTILI", "BUTTA IMMONDIZIA", "PULISCI CASA e baygon (no briciole)", "Partire con cell carichi", "Metti antifurti, togli programmazione"]
        cols_r = st.columns(3)
        for i, r in enumerate(racc): cols_r[i % 3].checkbox(r, key=f"r_{i}")

    f_piano = st.multiselect("📍 Filtra per Piano:", sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)]), default=sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)]))

    df_master['Quantità_Calc'] = df_master.apply(lambda x: calcola_final(x, giorni, pioggia_master, override_vento, st.session_state.cane_presente), axis=1)
    
    tabs = st.tabs(["🕺 Giorgio", "💃 Olga", "👧 Ilaria", "👶 Emma", "🏠 Comune & Cane"])
    nomi_p = ["Giorgio", "Olga", "Ilaria", "Emma", "Comune"]

    for i, tab in enumerate(tabs):
        with tab:
            nome_t = nomi_p[i]
            mask = (df_master['Proprietario'] == 'Comune') | (df_master['Proprietario'].str.contains('Cane', na=False, case=False)) if nome_t == "Comune" else (df_master['Proprietario'] == nome_t) | (df_master['Proprietario'] == 'Ciascuno')
            df_tab = df_master[mask & df_master['Posiz. piano'].astype(str).isin(f_piano)].copy()
            
            # Recupera lo stato salvato per ogni oggetto (chiave univoca: Nome_Oggetto)
            def get_stato_salvato(oggetto):
                chiave = f"{nome_t}_{oggetto}"
                return st.session_state.stati_globali.get(chiave, "⚪ Da fare")
                
            df_tab['Stato'] = df_tab['Oggetto'].apply(get_stato_salvato)
            
            # Mostra la tabella e cattura le modifiche
            df_edited = st.data_editor(
                df_tab[['Stato', 'Oggetto', 'Quantità_Calc', 'Posiz. piano', 'Note']], 
                column_config={
                    "Stato": st.column_config.SelectboxColumn("Stato", options=["⚪ Da fare", "🟠 In parte", "🟡 Ultimo min", "🔴 Zero", "🟢 FATTO"]), 
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
