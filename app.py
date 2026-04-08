import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests

# CONFIGURAZIONE PAGINA
st.set_page_config(page_title="Valigia Smart v2.3 - Famiglia Giorgio", layout="wide")

# 1. FUNZIONE METEO (Affidabile e senza chiavi API complicate)
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
        # File richiesto: Per viaggiare.csv (separatore ;)
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
    cane_presente = st.sidebar.toggle("Il cane viene con noi?", value=True)
    
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

    # --- MOTORE DI CALCOLO (CORRETTO) ---
    def calcola_smart(row, giorni, pioggia, vento, cane_ok):
        ogg = str(row['Oggetto']).lower()
        prop = str(row['Proprietario']).lower()
        
        # PRIORITÀ 1: IL CANE (Se il flag è spento, azzera tutto ciò che contiene "cane")
        if not cane_ok:
            if "cane" in prop or "cane:" in ogg:
                return 0
        
        # PRIORITÀ 2: ALLOGGIO (Hotel vs Appartamento)
        tipo_casa = str(row.get('Hotel / Appartamento / Entrambi', 'Entrambi')).strip()
        if alloggio == "Hotel" and tipo_casa == "Appartamento": return 0
        if alloggio == "Appartamento" and tipo_casa == "Hotel": return 0
        
        # PRIORITÀ 3: CONTESTO (Mare vs Montagna)
        contesto_row = str(row.get('Tipo viaggio / Contesto', 'Tutti'))
        if "Mare" in contesto_row and tipo_v != "Mare": return 0
        if "Montagna" in contesto_row and tipo_v != "Montagna": return 0
        
        # PRIORITÀ 4: QUANTITÀ DINAMICHE
        if "mutande" in ogg or "calze" in ogg: return giorni + 1
        if "magliette maniche corte" in ogg:
            # Bambine ricambio extra
            return giorni + 2 if ("ilaria" in prop or "emma" in prop) else giorni
        
        # PRIORITÀ 5: METEO
        if ("k-way" in ogg or "ombrellino" in ogg) and not pioggia: return 0
        if "ombrellone" in ogg and vento == "Forte": return 0

        # Se nessuna regola dinamica scatta, usa il valore Excel o 1
        try:
            val = row['Quantità']
            # Se la cella è vuota o non è un numero, mette 1
            if pd.isnull(val) or val == "": return 1
            return int(val)
        except: return 1

    # Applichiamo il calcolo
    df_master['Quantità_Calc'] = df_master.apply(lambda x: calcola_smart(x, giorni, pioggia, vento_descr, cane_presente), axis=1)

    # --- INTERFACCIA PRINCIPALE ---
    st.title(f"🧳 Valigia Smart: {citta}")
    
    # SEZIONE RACCOMANDAZIONI (Le tue 9 fisse)
    with st.expander("🚨 RACCOMANDAZIONI PRE-PARTENZA (Check-list Casa)", expanded=True):
        racc = [
            "Chiudo finestre mansarda e taverna", "Spengo NAS", "Coprire piscina",
            "Frutta in frigo giù nel sacchetto umido", "LASCIA A CASA LE COSE INUTILI",
            "BUTTA IMMONDIZIA", "PULISCI CASA e baygon (no briciole)",
            "Partire con cell carichi", "Metti antifurti, togli programmazione"
        ]
        cols = st.columns(3)
        for i, r in enumerate(racc):
            cols[i % 3].checkbox(r, key=f"r_{i}")

    # Filtro Piani
    piani = sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)])
    f_piano = st.multiselect("📍 Filtra per Piano (es. svuota la Taverna):", piani, default=piani)

    # Tabs per persone
    tabs = st.tabs(["Giorgio", "Olga", "Ilaria", "Emma", "Comune & Cane"])
    nomi_p = ["Giorgio", "Olga", "Ilaria", "Emma", "Comune"]

    for i, tab in enumerate(tabs):
        with tab:
            nome_tab = nomi_p[i]
            if nome_tab == "Comune":
                # Mostra Comune e Cane
                mask = (df_master['Proprietario'] == 'Comune') | (df_master['Proprietario'].str.contains('Cane', na=False, case=False))
            else:
                # Mostra Singolo e Ciascuno
                mask = (df_master['Proprietario'] == nome_tab) | (df_master['Proprietario'] == 'Ciascuno')
            
            df_tab = df_master[mask & df_master['Posiz. piano'].astype(str).isin(f_piano)].copy()
            df_tab['Stato'] = "⚪ Da fare"
            
            st.data_editor(
                df_tab[['Stato', 'Oggetto', 'Quantità_Calc', 'Posiz. piano', 'Note']],
                column_config={
                    "Stato": st.column_config.SelectboxColumn("Stato", options=["⚪ Da fare", "🟠 In parte", "🟡 Ultimo min", "🔴 Zero", "🟢 FATTO"]),
                    "Quantità_Calc": "Q.tà",
                    "Posiz. piano": "Piano"
                },
                hide_index=True, use_container_width=True, key=f"edit_{nome_tab}"
            )
