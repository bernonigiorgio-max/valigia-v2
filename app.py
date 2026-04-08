import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests

# CONFIGURAZIONE PAGINA
st.set_page_config(page_title="Valigia Smart v2.8 - Famiglia Giorgio", layout="wide")

# 1. FUNZIONE PER GENERARE LINK AERONAUTICA MILITARE
def get_meteoam_link(citta):
    # Formatta il nome città per l'URL del sito meteoam.it
    citta_url = citta.lower().replace(" ", "-")
    return f"https://www.meteoam.it/it/meteo-citta/{citta_url}"

# 2. FUNZIONE METEO AUTOMATICO (DI BACKUP/SUGGERIMENTO)
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
    citta = st.sidebar.text_input("Destinazione", "Alassio")
    d_inizio = st.sidebar.date_input("Data Arrivo", date.today())
    d_fine = st.sidebar.date_input("Data Partenza", date.today())
    
    giorni = (d_fine - d_inizio).days
    if giorni <= 0: giorni = 1
    
    st.sidebar.divider()
    tipo_v = st.sidebar.selectbox("Contesto", ["Mare", "Montagna", "Città"])
    alloggio = st.sidebar.radio("Soggiorno", ["Hotel", "Appartamento"])
    cane_presente = st.sidebar.toggle("Il cane viene con noi?", value=True)
    
    st.sidebar.divider()
    
    # --- NUOVA SEZIONE: METEO UFFICIALE AERONAUTICA ---
    st.sidebar.subheader("🌦️ Meteo Ufficiale")
    url_am = get_meteoam_link(citta)
    st.sidebar.link_button("Apri Meteo Aeronautica ↗️", url_am)
    
    st.sidebar.caption("Consulta il sito sopra e imposta qui sotto i dati reali:")
    
    # Recupero dati automatici solo come suggerimento visivo
    meteo_auto = get_weather_forecast(citta)
    p_sugg = max(meteo_auto['precipitation_probability_max']) > 30 if meteo_auto else False
    v_sugg = "Debole"
    if meteo_auto:
        v_max = max(meteo_auto['wind_speed_10m_max'])
        v_sugg = "Forte" if v_max > 30 else ("Medio" if v_max > 15 else "Debole")

    # CONTROLLI MANUALI (COMANDANO LA VALIGIA)
    override_cielo = st.sidebar.multiselect("Cielo (da MeteoAM):", ["Sole", "Nuvole", "Pioggia"], 
                                           default=["Pioggia"] if p_sugg else ["Sole"])
    override_vento = st.sidebar.select_slider("Vento (da MeteoAM):", options=["Debole", "Medio", "Forte"], 
                                             value=v_sugg)
    pioggia_master = "Pioggia" in override_cielo

    # --- MOTORE DI CALCOLO DINAMICO ---
    def calcola_final(row, giorni, pioggia_on, vento_livello, cane_ok):
        ogg = str(row['Oggetto']).lower()
        prop = str(row['Proprietario']).lower()
        
        if not cane_ok and ("cane" in prop or "cane:" in ogg): return 0
        
        tipo_casa = str(row.get('Hotel / Appartamento / Entrambi', 'Entrambi')).strip()
        if alloggio == "Hotel" and tipo_casa == "Appartamento": return 0
        if alloggio == "Appartamento" and tipo_casa == "Hotel": return 0
        
        cont_row = str(row.get('Tipo viaggio / Contesto', 'Tutti'))
        if "Mare" in cont_row and tipo_v != "Mare": return 0
        if "Montagna" in cont_row and tipo_v != "Montagna": return 0
        
        # Logica Quantità
        if "mutande" in ogg or "calze" in ogg: return giorni + 1
        if "magliette maniche corte" in ogg:
            return giorni + 2 if ("ilaria" in prop or "emma" in prop) else giorni
        
        # Logica Meteo Manuale (Comanda questa)
        if ("k-way" in ogg or "ombrellino" in ogg) and not pioggia_on: return 0
        if "ombrellone" in ogg and vento_livello == "Forte": return 0

        try:
            val = row['Quantità']
            if pd.isnull(val) or val == "" or val == "-1": return 1
            return int(val)
        except: return 1

    # --- INTERFACCIA PRINCIPALE ---
    st.title(f"🧳 Valigia Smart per {citta}")
    
    with st.expander("🚨 RACCOMANDAZIONI PRE-PARTENZA", expanded=True):
        racc = ["Chiudo finestre mansarda e taverna", "Spengo NAS", "Coprire piscina", "Frutta in frigo giù nel sacchetto umido", "LASCIA A CASA LE COSE INUTILI", "BUTTA IMMONDIZIA", "PULISCI CASA e baygon (no briciole)", "Partire con cell carichi", "Metti antifurti, togli programmazione"]
        cols_r = st.columns(3)
        for i, r in enumerate(racc): cols_r[i % 3].checkbox(r, key=f"r_{i}")

    f_piano = st.multiselect("📍 Filtra per Piano:", sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)]), default=sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)]))

    df_master['Quantità_Calc'] = df_master.apply(lambda x: calcola_final(x, giorni, pioggia_master, override_vento, cane_presente), axis=1)
    
    tabs = st.tabs(["🕺 Giorgio", "💃 Olga", "👧 Ilaria", "👶 Emma", "🏠 Comune & Cane"])
    nomi_p = ["Giorgio", "Olga", "Ilaria", "Emma", "Comune"]

    for i, tab in enumerate(tabs):
        with tab:
            nome_t = nomi_p[i]
            mask = (df_master['Proprietario'] == 'Comune') | (df_master['Proprietario'].str.contains('Cane', na=False, case=False)) if nome_t == "Comune" else (df_master['Proprietario'] == nome_t) | (df_master['Proprietario'] == 'Ciascuno')
            df_tab = df_master[mask & df_master['Posiz. piano'].astype(str).isin(f_piano)].copy()
            df_tab['Stato'] = "⚪ Da fare"
            st.data_editor(df_tab[['Stato', 'Oggetto', 'Quantità_Calc', 'Posiz. piano', 'Note']], column_config={"Stato": st.column_config.SelectboxColumn("Stato", options=["⚪ Da fare", "🟠 In parte", "🟡 Ultimo min", "🔴 Zero", "🟢 FATTO"]), "Quantità_Calc": "Q.tà", "Posiz. piano": "Piano", "Oggetto": st.column_config.TextColumn("Oggetto", disabled=True)}, hide_index=True, use_container_width=True, key=f"ed_{nome_t}")
