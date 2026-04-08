import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests

# CONFIGURAZIONE PAGINA
st.set_page_config(page_title="Valigia Smart v2.0 - Famiglia Giorgio", layout="wide")

# 1. FUNZIONE METEO (Open-Meteo: Gratis, No API Key)
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

# 2. CARICAMENTO DATI
@st.cache_data
def load_data():
    try:
        # Caricamento file richiesto: Per viaggiare.csv
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
    # --- SIDEBAR: PARAMETRI ---
    st.sidebar.header("📋 Setup Viaggio")
    citta = st.sidebar.text_input("Destinazione", "Alassio")
    d_inizio = st.sidebar.date_input("Data Arrivo", date.today())
    d_fine = st.sidebar.date_input("Data Partenza", date.today())
    
    giorni = (d_fine - d_inizio).days
    if giorni <= 0: giorni = 1
    
    st.sidebar.divider()
    tipo_v = st.sidebar.selectbox("Contesto", ["Mare", "Montagna", "Città"])
    alloggio = st.sidebar.radio("Soggiorno", ["Hotel", "Appartamento"])
    
    # --- ELABORAZIONE METEO ---
    meteo_info = get_weather_forecast(citta)
    if meteo_info:
        t_max = max(meteo_info['temperature_2m_max'])
        pioggia = max(meteo_info['precipitation_probability_max']) > 30
        v_max = max(meteo_info['wind_speed_10m_max'])
        vento_descr = "Forte" if v_max > 30 else ("Medio" if v_max > 15 else "Debole")
    else:
        t_max, pioggia, vento_descr = 22, False, "Debole"

    st.sidebar.info(f"☀️ Meteo previsto: {t_max}°C | 🌬️ Vento: {vento_descr} | 🌧️ Pioggia: {'Sì' if pioggia else 'No'}")

    # --- MOTORE DI CALCOLO ---
    def calcola_smart(row, giorni, pioggia, vento):
        # Filtro Hotel / Appartamento (Logica Rigida)
        tipo_casa = str(row.get('Hotel / Appartamento / Entrambi', 'Entrambi')).strip()
        if alloggio == "Hotel" and tipo_casa == "Appartamento": return 0
        if alloggio == "Appartamento" and tipo_casa == "Hotel": return 0
        
        # Filtro Contesto
        contesto_row = str(row.get('Tipo viaggio / Contesto', 'Tutti'))
        if "Mare" in contesto_row and tipo_v != "Mare": return 0
        if "Montagna" in contesto_row and tipo_v != "Montagna": return 0
        
        ogg = str(row['Oggetto']).lower()
        prop = str(row['Proprietario'])
        
        if "mutande" in ogg or "calze" in ogg: return giorni + 1
        if "magliette maniche corte" in ogg:
            return giorni + 2 if ("Ilaria" in prop or "Emma" in prop) else giorni
        
        if ("k-way" in ogg or "ombrellino" in ogg) and not pioggia: return 0
        if "ombrellone" in ogg and vento == "Forte": return 0

        try:
            val = row['Quantità']
            return int(val) if pd.notnull(val) else 1
        except: return 1

    df_master['Quantità_Calc'] = df_master.apply(lambda x: calcola_smart(x, giorni, pioggia, vento_descr), axis=1)

    # --- INTERFACCIA PRINCIPALE ---
    st.title(f"🧳 Valigia Smart: {citta}")
    
    # SEZIONE RACCOMANDAZIONI (Fisse come richiesto)
    with st.expander("🚨 RACCOMANDAZIONI PRE-PARTENZA (Check-list Casa)", expanded=True):
        col1, col2 = st.columns(2)
        racc = [
            "Chiudo finestre mansarda e taverna", "Spengo NAS", "Coprire piscina",
            "Frutta in frigo giù nel sacchetto umido", "LASCIA A CASA LE COSE INUTILI",
            "BUTTA IMMONDIZIA", "PULISCI CASA e baygon (no briciole)",
            "Partire con cell carichi", "Metti antifurti, togli programmazione"
        ]
        for i, r in enumerate(racc):
            if i % 2 == 0: col1.checkbox(r, key=f"r_{i}")
            else: col2.checkbox(r, key=f"r_{i}")

    # Filtro Piani
    piani = sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)])
    f_piano = st.multiselect("📍 Filtra per Piano:", piani, default=piani)

    tabs = st.tabs(["Giorgio", "Olga", "Ilaria", "Emma", "Comune & Cane"])
    nomi_p = ["Giorgio", "Olga", "Ilaria", "Emma", "Comune"]

    for i, tab in enumerate(tabs):
        with tab:
            nome = nomi_p[i]
            if nome == "Comune":
                mask = (df_master['Proprietario'] == 'Comune') | (df_master['Proprietario'].str.contains('Cane', na=False, case=False))
            else:
                mask = (df_master['Proprietario'] == nome) | (df_master['Proprietario'] == 'Ciascuno')
            
            df_tab = df_master[mask & df_master['Posiz. piano'].astype(str).isin(f_piano)].copy()
            df_tab['Stato'] = "⚪ Da fare"
            
            st.data_editor(
                df_tab[['Stato', 'Oggetto', 'Quantità_Calc', 'Posiz. piano', 'Note']],
                column_config={
                    "Stato": st.column_config.SelectboxColumn("Stato", options=["⚪ Da fare", "🟠 In parte", "🟡 Ultimo min", "🔴 Zero", "🟢 FATTO"]),
                    "Quantità_Calc": "Q.tà",
                    "Posiz. piano": "Piano"
                },
                hide_index=True, use_container_width=True, key=f"edit_{nome}"
            )
