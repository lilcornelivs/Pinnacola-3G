import streamlit as st
import pandas as pd
import requests
import time

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Pinnacola Triello", layout="wide")

# CSS ANTI-APPANNAMENTO E PULIZIA
st.markdown("""
    <style>
    [data-stale="true"], div[data-fragment-id], [data-testid="stAppViewBlockContainer"] > div {
        opacity: 1 !important; filter: none !important; transition: none !important;
    }
    [data-testid="stStatusWidget"] { display: none !important; }
    * { transition: none !important; animation: none !important; }
    </style>
    """, unsafe_allow_html=True)

# !!! INCOLLA QUI SOTTO IL NUOVO LINK APPS SCRIPT !!!
API_URL = "INCOLLA_QUI_IL_TUO_NUOVO_LINK_EXEC"

def get_data():
    cols = ["partita", "mano", "p1", "p2", "p3", "chi"]
    try:
        r = requests.get(API_URL)
        data = r.json()
        if not data: return pd.DataFrame(columns=cols)
        df_raw = pd.DataFrame(data)
        # Assicuriamoci che ci siano tutte le colonne
        for c in cols:
            if c not in df_raw.columns: df_raw[c] = 0 if c != 'chi' else ""
        
        # Conversione numeri
        for col in ['partita', 'mano', 'p1', 'p2', 'p3']:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0).astype(int)
        return df_raw
    except:
        return pd.DataFrame(columns=cols)

# --- CARICAMENTO INIZIALE ---
df_init = get_data()
soglia_default = 1500
if not df_init.empty:
    c_rows = df_init[df_init['chi'] == 'CONFIG']
    if not c_rows.empty:
        soglia_default = int(c_rows.iloc[-1]['partita'])

# --- SIDEBAR ---
with st.sidebar:
    st.header("Impostazioni")
    soglia_scelta = st.number_input("Soglia Vittoria", value=soglia_default, step=100)
    if st.button("💾 Salva Soglia"):
        requests.post(API_URL, json={"action": "set_soglia", "valore": int(soglia_scelta)})
        st.success("Salvata!")
        time.sleep(1)
        st.rerun()
    st.divider()
    if st.button("🗑️ Reset Totale"):
        requests.post(API_URL, json={"action": "reset"})
        st.rerun()

st.title("🃏 Mufi vs Mina vs Corni")

# --- DASHBOARD TEMPO REALE ---
@st.fragment(run_every="2s") 
def live_dashboard(s_val):
    data = get_data()
    # Filtra righe di sistema
    df_p = data[~data['chi'].isin(['CONFIG', 'WIN_MUFI', 'WIN_MINA', 'WIN_CORNI'])] if not data.empty else data
    
    # Calcolo Vittorie (Medagliere)
    v_mufi = len(data[data['chi'] == 'WIN_MUFI']) if not data.empty else 0
    v_mina = len(data[data['chi'] == 'WIN_MINA']) if not data.empty else 0
    v_corni = len(data[data['chi'] == 'WIN_CORNI']) if not data.empty else 0
    
    n_p, t1, t2, t3 = 1, 0, 0, 0
    if not df_p.empty:
        n_p = int(df_p['partita'].max())
        curr = df_p[df_p['partita'] == n_p]
        t1, t2, t3 = curr['p1'].sum(), curr['p2'].sum(), curr['p3'].sum()

    # Visualizzazione
    c1, c2, c3 = st.columns(3)
    c1.subheader(f"🏆 Mufi: {v_mufi}")
    c2.subheader(f"🏆 Mina: {v_mina}")
    c3.subheader(f"🏆 Corni: {v_corni}")
    st.divider()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("MUFI", int(t1))
    m2.metric("MINA", int(t2))
    m3.metric("CORNI", int(t3))
    
    st.divider()
    st.subheader("📜 Storico Partita")
    if not df_p.empty:
        disp = df_p[(df_p['partita'] == n_p) & (~df_p['chi'].isin(['START']))].sort_values(by="mano", ascending=False)
        st.table(disp[['partita', 'mano', 'p1', 'p2', 'p3', 'chi']].rename(
            columns={'partita':'Partita','mano':'Mano','p1':'Mufi','p2':'Mina','p3':'Corni','chi':'Chiusura'}
        ))
    return n_p, t1, t2, t3

n_partita, tot1, tot2, tot3 = live_dashboard(soglia_scelta)

# --- LOGICA DI GIOCO ---
game_over = False
max_punti = max(tot1, tot2, tot3)

if max_punti >= soglia_scelta:
    # Controlliamo se c'è un pareggio tra i primi
    count_max = [tot1, tot2, tot3].count(max_punti)
    if count_max > 1:
        st.warning(f"⚠️ Pareggio a {max_punti}! Si continua.")
    else:
        game_over = True

if not game_over:
    st.write("---")
    st.subheader("📝 Registra Mano")
    
    # Campi input SENZA FORM (Fix bug focus)
    col1, col2, col3, col4 = st.columns(4)
    # Usiamo chiavi univoche per mantenere lo stato
    val1 = col1.number_input("Punti Mufi", value=None, placeholder="-30, 50...", step=5, key="in_mufi", min_value=-5000)
    val2 = col2.number_input("Punti Mina", value=None, placeholder="-30, 50...", step=5, key="in_mina", min_value=-5000)
    val3 = col3.number_input("Punti Corni", value=None, placeholder="-30, 50...", step=5, key="in_corni", min_value=-5000)
    chi_chiude = col4.selectbox("Chi ha chiuso?", ["Nessuno", "Mufi", "Mina", "Corni"], key="in_chi")
    
    # Bottone diretto
    if st.button("REGISTRA MANO", type="primary"):
        temp_df = get_data()
        # Calcolo mano corretta
        mani_partita = temp_df[(temp_df['partita'] == n_partita) & (~temp_df['chi'].isin(['START', 'WIN_MUFI', 'WIN_MINA', 'WIN_CORNI', 'CONFIG']))]
        nuova_mano = len(mani_partita) + 1
        
        requests.post(API_URL, json={
            "action": "add", "partita": n_partita, "mano": nuova_mano,
            "p1": val1 if val1 else 0, 
            "p2": val2 if val2 else 0, 
            "p3": val3 if val3 else 0, 
            "chi": chi_chiude
        })
        st.rerun()
else:
    # VITTORIA
    st.balloons()
    if tot1 == max_punti: vincitore, w_code = "Mufi", "WIN_MUFI"
    elif tot2 == max_punti: vincitore, w_code = "Mina", "WIN_MINA"
    else: vincitore, w_code = "Corni", "WIN_CORNI"
    
    st.success(f"🏆 {vincitore.upper()} HA VINTO!")
    st.metric("Punteggio Finale", f"{tot1} - {tot2} - {tot3}")
    
    if st.button("🏁 SALVA E NUOVA PARTITA"):
        # Salva vittoria
        requests.post(API_URL, json={"action": "add", "partita": n_partita, "mano": 999, "p1":0,"p2":0,"p3":0, "chi": w_code})
        # Nuova partita
        requests.post(API_URL, json={"action": "add", "partita": n_partita + 1, "mano": 0, "p1":0,"p2":0,"p3":0, "chi": "START"})
        st.rerun()
