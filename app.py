import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests

# CONFIGURAZIONE PAGINA
st.set_page_config(page_title="Valigia Smart v2.5 - Famiglia Giorgio", layout="wide")

# 1. FUNZIONE METEO AUTOMATICO
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
        # Carica il file Per viaggiare.csv (separatore punto e virgola)
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
    # --- SIDEBAR: PARAMETRI FISSI ---
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
    
    # --- RECUPERO METEO AUTOMATICO (PER SUGGERIMENTO) ---
    meteo_auto = get_weather_forecast(citta)
    p_suggerita = False
    v_suggerito = "Debole"
    
    if meteo_auto:
        p_suggerita = max(meteo_auto['precipitation_probability_max']) > 30
        v_max_auto = max(meteo_auto['wind_speed_10m_max'])
        v_suggerito = "Forte" if v_max_auto > 30 else ("Medio" if v_max_auto > 15 else "Debole")

    # --- INTERFACCIA PRINCIPALE ---
    st.title(f"🧳 Valigia Smart per {citta}")
    st.write(f"Soggiorno di **{giorni} giorni**")

    # SEZIONE RACCOMANDAZIONI
    with st.expander("🚨 RACCOMANDAZIONI PRE-PARTENZA (Check-list Casa)", expanded=True):
        racc = [
            "Chiudo finestre mansarda e taverna", "Spengo NAS", "Coprire piscina",
            "Frutta in frigo giù nel sacchetto umido", "LASCIA A CASA LE COSE INUTILI",
            "BUTTA IMMONDIZIA", "PULISCI CASA e baygon (no briciole)",
            "Partire con cell carichi", "Metti antifurti, togli programmazione"
        ]
        cols_r = st.columns(3)
        for i, r in enumerate(racc):
            cols_r[i % 3].checkbox(r, key=f"r_{i}")

    # FILTRO PIANI
    piani = sorted([str(p) for p in df_master['Posiz. piano'].unique() if pd.notnull(p)])
    f_piano = st.multiselect("📍 Filtra per Piano (dove sono le cose):", piani, default=piani)

    # --- MOTORE DI CALCOLO DINAMICO ---
    def calcola_final(row, giorni, pioggia_on, vento_livello, cane_ok):
        ogg = str(row['Oggetto']).lower()
        prop = str(row['Proprietario']).lower()
        
        # 1. Filtro Cane (Agisce su proprietario o nome oggetto)
        if not cane_ok and ("cane" in prop or "cane:" in ogg):
            return 0
        
        # 2. Filtro Alloggio
        tipo_casa = str(row.get('Hotel / Appartamento / Entrambi', 'Entrambi')).strip()
        if alloggio == "Hotel" and tipo_casa == "Appartamento": return 0
        if alloggio == "Appartamento" and tipo_casa == "Hotel": return 0
        
        # 3. Filtro Contesto
        contesto_row = str(row.get('Tipo viaggio / Contesto', 'Tutti'))
        if "Mare" in contesto_row and tipo_v != "Mare": return 0
        if "Montagna" in contesto_row and tipo_v != "Montagna": return 0
        
        # 4. Quantità basate sui giorni
        if "mutande" in ogg or "calze" in ogg: return giorni + 1
        if "magliette maniche corte" in ogg:
            # Maglie extra per Ilaria (2015) ed Emma (2017)
            return giorni + 2 if ("ilaria" in prop or "emma" in prop) else giorni
        
        # 5. Logica Meteo (Manuale/Automatico)
        if ("k-way" in ogg or "ombrellino" in ogg) and not pioggia_on: return 0
        if "ombrellone" in ogg and vento_livello == "Forte": return 0

        # Ritorna valore manuale se presente, altrimenti 1
        try:
            val = row['Quantità']
            return int(val) if pd.notnull(val) and val != "" else 1
        except: return 1

    # --- LAYOUT TABELLE + OVERRIDE METEO ---
    main_col, side_col = st.columns([4, 1])

    with side_col:
        st.subheader("🌦️ Controllo Meteo")
        st.info(f"Suggerito: {'Pioggia' if p_suggerita else 'Sole'}, Vento {v_suggerito}")
        override_cielo = st.multiselect("Condizioni:", ["Sole", "Nuvole", "Pioggia"], 
                                       default=["Pioggia"] if p_suggerita else ["Sole"])
        override_vento = st.select_slider("Intensità Vento:", options=["Debole", "Medio", "Forte"], 
                                         value=v_suggerito)
        pioggia_attiva = "Pioggia" in override_cielo

    with main_col:
        # Applichiamo il calcolo con le variabili manuali
        df_master['Quantità_Calc'] = df_master.apply(
            lambda x: calcola_final(x, giorni, pioggia_attiva, override_vento, cane_presente), axis=1
        )
        
        tabs = st.tabs(["🕺 Giorgio", "💃 Olga", "👧 Ilaria", "👶 Emma", "🏠 Comune & Cane"])
        nomi_p = ["Giorgio", "Olga", "Ilaria", "Emma", "Comune"]

        for i, tab in enumerate(tabs):
            with tab:
                nome_t = nomi_p[i]
                if nome_t == "Comune":
                    mask = (df_master['Proprietario'] == 'Comune') | (df_master['Proprietario'].str.contains('Cane', na=False, case=False))
                else:
                    mask = (df_master['Proprietario'] == nome_t) | (df_master['Proprietario'] == 'Ciascuno')
                
                df_tab = df_master[mask & df_master['Posiz. piano'].astype(str).isin(f_piano)].copy()
                df_tab['Stato'] = "⚪ Da fare"
                
                st.data_editor(
                    df_tab[['Stato', 'Oggetto', 'Quantità_Calc', 'Posiz. piano', 'Note']],
                    column_config={
                        "Stato": st.column_config.SelectboxColumn("Stato", 
                            options=["⚪ Da fare", "🟠 In parte", "🟡 Ultimo min", "🔴 Zero", "🟢 FATTO"]),
                        "Quantità_Calc": "Q.tà",
                        "Posiz. piano": "Piano",
                        "Oggetto": st.column_config.TextColumn("Oggetto", disabled=True)
                    },
                    hide_index=True, use_container_width=True, key=f"ed_{nome_t}"
                )
