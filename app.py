import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Triello Pinnacola", layout="wide")

# CSS ANTI-APPANNAMENTO
st.markdown("""
    <style>
    [data-stale="true"], div[data-fragment-id], [data-testid="stAppViewBlockContainer"] > div {
        opacity: 1 !important; filter: none !important; transition: none !important;
    }
    [data-testid="stStatusWidget"] { display: none !important; }
    * { transition: none !important; animation: none !important; }
    </style>
    """, unsafe_allow_html=True)

# !!! INCOLLA QUI IL NUOVO LINK APPS SCRIPT !!!
API_URL = "https://script.google.com/macros/s/AKfycbwxYgc7EvSqSCqfcKwoddtnWRXnWTmmc75l2C5APziOfw-4TUBvZI99uwn3Y_1VrtYp3Q/exec"

def get_data():
    cols = ["partita", "mano", "p1", "p2", "p3", "chi"]
    try:
        r = requests.get(API_URL)
        data = r.json()
        if not data: return pd.DataFrame(columns=cols)
        df_raw = pd.DataFrame(data)
        for c in cols:
            if c not in df_raw.columns: df_raw[c] = 0 if c != 'chi' else ""
        for col in ['partita', 'mano', 'p1', 'p2', 'p3']:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0).astype(int)
        return df_raw
    except:
        return pd.DataFrame(columns=cols)

# --- CARICAMENTO CONFIGURAZIONE ---
df_init = get_data()
target_default = 1500
mode_default = 0 # 0 = Punti, 1 = Mani

if not df_init.empty:
    c_rows = df_init[df_init['chi'] == 'CONFIG']
    if not c_rows.empty:
        # Colonna 'partita' ha il valore, colonna 'mano' ha la modalità
        target_default = int(c_rows.iloc[-1]['partita'])
        mode_default = int(c_rows.iloc[-1]['mano'])

# --- SIDEBAR (Scelta Modalità) ---
with st.sidebar:
    st.header("Impostazioni Partita")
    
    # Selettore Modalità
    modo_scelto_str = st.radio("Modalità di Gioco:", ["A Punti (Soglia)", "Numero di Mani Fisse"], 
                               index=0 if mode_default == 0 else 1)
    
    valore_impostato = 0
    modo_code = 0
    
    if modo_scelto_str == "A Punti (Soglia)":
        modo_code = 0
        valore_impostato = st.number_input("Soglia Vittoria", value=target_default if mode_default==0 else 1500, step=100)
    else:
        modo_code = 1
        valore_impostato = st.number_input("Numero di Mani da giocare", value=target_default if mode_default==1 else 3, step=1)

    if st.button("💾 Salva Impostazioni"):
        # Salviamo sia il valore che la modalità
        requests.post(API_URL, json={"action": "set_config", "valore": int(valore_impostato), "modalita": modo_code})
        st.success(f"Impostato: {modo_scelto_str} a {valore_impostato}")
        time.sleep(1)
        st.rerun()
        
    st.divider()
    if st.button("🗑️ Reset Totale"):
        requests.post(API_URL, json={"action": "reset"})
        st.rerun()

# Titolo Dinamico
if mode_default == 0:
    st.title(f"🃏 Triello a Punti (Soglia: {target_default})")
else:
    st.title(f"🃏 Triello a Mani (Totale Mani: {target_default})")

# --- DASHBOARD TEMPO REALE ---
@st.fragment(run_every="2s") 
def live_dashboard(target, mode):
    data = get_data()
    df_p = data[~data['chi'].isin(['CONFIG', 'WIN_MUFI', 'WIN_MINA', 'WIN_CORNI'])] if not data.empty else data
    
    v_mufi = len(data[data['chi'] == 'WIN_MUFI']) if not data.empty else 0
    v_mina = len(data[data['chi'] == 'WIN_MINA']) if not data.empty else 0
    v_corni = len(data[data['chi'] == 'WIN_CORNI']) if not data.empty else 0
    
    n_p, t1, t2, t3, mani_giocate = 1, 0, 0, 0, 0
    if not df_p.empty:
        n_p = int(df_p['partita'].max())
        curr = df_p[df_p['partita'] == n_p]
        # Escludiamo lo START per contare le mani giocate
        curr_mani = curr[curr['chi'] != 'START']
        mani_giocate = len(curr_mani)
        t1, t2, t3 = curr['p1'].sum(), curr['p2'].sum(), curr['p3'].sum()

    # Visualizzazione Medagliere
    c1, c2, c3 = st.columns(3)
    c1.subheader(f"🏆 Mufi: {v_mufi}")
    c2.subheader(f"🏆 Mina: {v_mina}")
    c3.subheader(f"🏆 Corni: {v_corni}")
    st.divider()
    
    # Visualizzazione Punteggi
    m1, m2, m3 = st.columns(3)
    m1.metric("MUFI", int(t1))
    m2.metric("MINA", int(t2))
    m3.metric("CORNI", int(t3))
    
    # Info extra se a mani fisse
    if mode == 1:
        st.progress(min(mani_giocate / target, 1.0))
        st.caption(f"Mano {mani_giocate} su {target}")

    st.divider()
    st.subheader("📜 Storico Partita")
    if not df_p.empty:
        disp = df_p[(df_p['partita'] == n_p) & (~df_p['chi'].isin(['START']))].sort_values(by="mano", ascending=False)
        st.table(disp[['partita', 'mano', 'p1', 'p2', 'p3', 'chi']].rename(
            columns={'partita':'Partita','mano':'Mano','p1':'Mufi','p2':'Mina','p3':'Corni','chi':'Chiusura'}
        ))
    return n_p, t1, t2, t3, mani_giocate

n_partita, tot1, tot2, tot3, mani_attuali = live_dashboard(target_default, mode_default)

# --- LOGICA DI GIOCO (IBRIDA) ---
game_over = False
max_punti = max(tot1, tot2, tot3)
messaggio_vittoria = ""
vincitore_code = ""

if mode_default == 0:
    # --- MODALITÀ SOGLIA PUNTI ---
    if max_punti >= target_default:
        count_max = [tot1, tot2, tot3].count(max_punti)
        if count_max > 1:
            st.warning(f"⚠️ Pareggio a {max_punti}! Si continua finché uno supera gli altri.")
        else:
            game_over = True
else:
    # --- MODALITÀ MANI FISSE ---
    if mani_attuali >= target_default:
        game_over = True
        # Qui i pareggi sono accettati

if not game_over:
    st.write("---")
    st.subheader("📝 Registra Mano")
    
    col1, col2, col3, col4 = st.columns(4)
    val1 = col1.number_input("Punti Mufi", value=None, placeholder="...", step=5, key="i_mufi", min_value=-5000)
    val2 = col2.number_input("Punti Mina", value=None, placeholder="...", step=5, key="i_mina", min_value=-5000)
    val3 = col3.number_input("Punti Corni", value=None, placeholder="...", step=5, key="i_corni", min_value=-5000)
    chi_chiude = col4.selectbox("Chi ha chiuso?", ["Nessuno", "Mufi", "Mina", "Corni"], key="i_chi")
    
    if st.button("REGISTRA MANO", type="primary"):
        temp_df = get_data()
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
    # --- FINE PARTITA ---
    st.balloons()
    
    # Calcolo Vincitori (Gestione Parimerito)
    vincitori = []
    if tot1 == max_punti: vincitori.append("Mufi")
    if tot2 == max_punti: vincitori.append("Mina")
    if tot3 == max_punti: vincitori.append("Corni")
    
    if len(vincitori) == 1:
        st.success(f"🏆 {vincitori[0].upper()} HA VINTO!")
        if vincitori[0] == "Mufi": vincitore_code = "WIN_MUFI"
        elif vincitori[0] == "Mina": vincitore_code = "WIN_MINA"
        else: vincitore_code = "WIN_CORNI"
    else:
        # CASO PAREGGIO (A mani fisse)
        nomi = " e ".join(vincitori)
        st.warning(f"🤝 PAREGGIO TRA: {nomi.upper()}!")
        vincitore_code = "DRAW" # O puoi decidere di non assegnare coppe
        
    st.metric("Punteggio Finale", f"{tot1} - {tot2} - {tot3}")
    
    if st.button("🏁 SALVA E NUOVA PARTITA"):
        # Se è pareggio, magari non salviamo la coppa, o salviamo una riga speciale DRAW
        # Qui salvo la vittoria solo se c'è un vincitore unico, oppure puoi decidere tu
        if len(vincitori) == 1:
            requests.post(API_URL, json={"action": "add", "partita": n_partita, "mano": 999, "p1":0,"p2":0,"p3":0, "chi": vincitore_code})
        else:
             # Se vuoi contare i pareggi, potresti inventarti WIN_DRAW, ma per ora non conta nulla nel medagliere
             requests.post(API_URL, json={"action": "add", "partita": n_partita, "mano": 999, "p1":0,"p2":0,"p3":0, "chi": "DRAW"})

        requests.post(API_URL, json={"action": "add", "partita": n_partita + 1, "mano": 0, "p1":0,"p2":0,"p3":0, "chi": "START"})
        st.rerun()
