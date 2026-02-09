import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Triello Mufi-Mina-Corni", layout="wide")

# CSS PER STABILIZZARE LO SCHERMO
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
API_URL = "https://script.google.com/macros/s/AKfycbwal0WLyedh8EuH5mdhIrnX36hH3FzMK9i3FCwR5HpVNMGZvGpVkg11kbF3ZEf6l43CpA/exec"

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
soglia_default = 1500
mode_default = 0   # 0 = A Soglia, 1 = Numero Fisso
num_partite_target = 3 # Default 3 partite

if not df_init.empty:
    c_rows = df_init[df_init['chi'] == 'CONFIG']
    if not c_rows.empty:
        last_conf = c_rows.iloc[-1]
        soglia_default = int(last_conf['partita']) # Colonna 1
        mode_default = int(last_conf['mano'])      # Colonna 2
        num_partite_target = int(last_conf['p1'])  # Colonna 3

# --- SIDEBAR IMPOSTAZIONI ---
with st.sidebar:
    st.header("Impostazioni")
    
    # Scelta Modalità
    modo_scelto = st.radio("Modalità di Gioco:", ["A Punti (Soglia)", "Numero Fisso di Partite"], 
                           index=0 if mode_default == 0 else 1)
    
    valore_soglia = 1500
    valore_partite = 3
    
    if modo_scelto == "A Punti (Soglia)":
        valore_soglia = st.number_input("Punti per vincere", value=soglia_default if mode_default==0 else 1500, step=100)
        # Se siamo in modo soglia, il target partite non conta, ma lo passiamo comunque
        valore_partite = num_partite_target
        new_mode = 0
    else:
        st.info("In questa modalità giocherete un numero fisso di mani (che chiamiamo Partite). Alla fine vince chi ha più punti.")
        valore_partite = st.number_input("Quante Partite vuoi giocare?", value=num_partite_target if mode_default==1 else 3, step=1)
        valore_soglia = soglia_default # Manteniamo la vecchia soglia per memoria
        new_mode = 1

    if st.button("💾 Salva e Riavvia"):
        # Salviamo tutto nel database
        requests.post(API_URL, json={
            "action": "set_config", 
            "valore": int(valore_soglia), 
            "modalita": int(new_mode),
            "num_partite": int(valore_partite)
        })
        st.success("Configurazione Salvata!")
        time.sleep(1)
        st.rerun()
        
    st.divider()
    if st.button("🗑️ Reset Totale"):
        requests.post(API_URL, json={"action": "reset"})
        st.rerun()

# Titolo Dinamico
if mode_default == 0:
    st.title(f"🃏 Pinnacola a Punti (Vince chi fa {soglia_default})")
else:
    st.title(f"🃏 Pinnacola a Partite Fisse (Totale: {num_partite_target})")

# --- DASHBOARD TEMPO REALE ---
@st.fragment(run_every="2s") 
def live_dashboard(target_pts, target_games, mode):
    data = get_data()
    # Filtriamo i dati puliti (senza config e senza vecchie vittorie salvate)
    df_p = data[~data['chi'].isin(['CONFIG', 'WIN_MUFI', 'WIN_MINA', 'WIN_CORNI'])] if not data.empty else data
    
    # Conteggio Coppe (Medagliere storico)
    v_mufi = len(data[data['chi'] == 'WIN_MUFI']) if not data.empty else 0
    v_mina = len(data[data['chi'] == 'WIN_MINA']) if not data.empty else 0
    v_corni = len(data[data['chi'] == 'WIN_CORNI']) if not data.empty else 0
    
    n_p, t1, t2, t3, giocate_attuali = 1, 0, 0, 0, 0
    
    if not df_p.empty:
        n_p = int(df_p['partita'].max()) # Questo è l'ID del torneo corrente
        curr = df_p[df_p['partita'] == n_p]
        
        # Escludiamo la riga START per contare quante mani/partite abbiamo giocato
        giocate_df = curr[curr['chi'] != 'START']
        giocate_attuali = len(giocate_df)
        
        t1, t2, t3 = curr['p1'].sum(), curr['p2'].sum(), curr['p3'].sum()

    # Visualizzazione Coppe
    c1, c2, c3 = st.columns(3)
    c1.subheader(f"🏆 Mufi: {v_mufi}")
    c2.subheader(f"🏆 Mina: {v_mina}")
    c3.subheader(f"🏆 Corni: {v_corni}")
    st.divider()
    
    # Barra progresso se siamo a Partite Fisse
    if mode == 1:
        st.write(f"📊 **Stato Torneo:** Giocata partita **{giocate_attuali}** su **{target_games}**")
        if target_games > 0:
            st.progress(min(giocate_attuali / target_games, 1.0))
    
    # Punteggi Correnti
    m1, m2, m3 = st.columns(3)
    m1.metric("MUFI", int(t1))
    m2.metric("MINA", int(t2))
    m3.metric("CORNI", int(t3))
    
    st.divider()
    st.subheader("📜 Storico (Ultime giocate)")
    if not df_p.empty:
        disp = df_p[(df_p['partita'] == n_p) & (~df_p['chi'].isin(['START']))].sort_values(by="mano", ascending=False)
        st.table(disp[['partita', 'mano', 'p1', 'p2', 'p3', 'chi']].rename(
            columns={'partita':'Torneo ID','mano':'Partita N.','p1':'Mufi','p2':'Mina','p3':'Corni','chi':'Chi ha chiuso'}
        ))
    return n_p, t1, t2, t3, giocate_attuali

n_torneo, tot1, tot2, tot3, partite_fatte = live_dashboard(soglia_default, num_partite_target, mode_default)

# --- LOGICA DI GIOCO ---
game_over = False

if mode_default == 0:
    # --- MODALITÀ SOGLIA ---
    max_p = max(tot1, tot2, tot3)
    if max_p >= soglia_default:
        if [tot1, tot2, tot3].count(max_p) > 1:
            st.warning(f"⚠️ Pareggio a {max_p}! Si continua.")
        else:
            game_over = True
else:
    # --- MODALITÀ NUMERO FISSO ---
    # Se abbiamo giocato il numero di partite richiesto (o di più), finisce.
    if partite_fatte >= num_partite_target:
        game_over = True

if not game_over:
    st.write("---")
    st.subheader("📝 Registra Risultato Partita")
    
    # Input Campi
    col1, col2, col3, col4 = st.columns(4)
    val1 = col1.number_input("Punti Mufi", value=None, placeholder="...", step=5, key="i_mufi", min_value=-5000)
    val2 = col2.number_input("Punti Mina", value=None, placeholder="...", step=5, key="i_mina", min_value=-5000)
    val3 = col3.number_input("Punti Corni", value=None, placeholder="...", step=5, key="i_corni", min_value=-5000)
    chi_chiude = col4.selectbox("Chi ha chiuso?", ["Nessuno", "Mufi", "Mina", "Corni"], key="i_chi")
    
    if st.button("REGISTRA PARTITA", type="primary"):
        # Calcolo ID progressivo della "mano" (che qui chiamiamo Partita nel torneo)
        temp_df = get_data()
        mani_reali = temp_df[(temp_df['partita'] == n_torneo) & (~temp_df['chi'].isin(['START', 'WIN_MUFI', 'WIN_MINA', 'WIN_CORNI', 'CONFIG']))]
        nuova_mano_id = len(mani_reali) + 1
        
        requests.post(API_URL, json={
            "action": "add", "partita": n_torneo, "mano": nuova_mano_id,
            "p1": val1 if val1 else 0, 
            "p2": val2 if val2 else 0, 
            "p3": val3 if val3 else 0, 
            "chi": chi_chiude
        })
        st.rerun()

else:
    # --- FINE TORNEO / FINE SOGLIA ---
    st.balloons()
    
    # Calcolo Classifica Finale
    classifica = [
        {"nome": "Mufi", "punti": tot1},
        {"nome": "Mina", "punti": tot2},
        {"nome": "Corni", "punti": tot3}
    ]
    # Ordina decrescente
    classifica.sort(key=lambda x: x["punti"], reverse=True)
    
    st.title("🏁 TORNEO COMPLETATO!")
    st.subheader("🥇 PODIO FINALE")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🥇 1° POSTO", f"{classifica[0]['nome']}", f"{classifica[0]['punti']} pts")
    col2.metric("🥈 2° POSTO", f"{classifica[1]['nome']}", f"{classifica[1]['punti']} pts")
    col3.metric("🥉 3° POSTO", f"{classifica[2]['nome']}", f"{classifica[2]['punti']} pts")
    
    # Determinazione vincitore per il Medagliere
    # Se c'è pareggio al primo posto, gestiamo:
    if classifica[0]["punti"] == classifica[1]["punti"]:
        st.warning("⚠️ PAREGGIO AL PRIMO POSTO! Nessuna coppa assegnata automaticamente.")
        win_code = "DRAW"
    else:
        winner = classifica[0]["nome"]
        if winner == "Mufi": win_code = "WIN_MUFI"
        elif winner == "Mina": win_code = "WIN_MINA"
        else: win_code = "WIN_CORNI"
    
    st.write("---")
    if st.button("🏆 SALVA VITTORIA E INIZIA NUOVO TORNEO"):
        # 1. Salva la coppa
        if win_code != "DRAW":
            requests.post(API_URL, json={"action": "add", "partita": n_torneo, "mano": 999, "p1":0,"p2":0,"p3":0, "chi": win_code})
        
        # 2. Inizia nuovo torneo (ID + 1)
        requests.post(API_URL, json={"action": "add", "partita": n_torneo + 1, "mano": 0, "p1":0,"p2":0,"p3":0, "chi": "START"})
        st.rerun()
