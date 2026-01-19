import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. KONFIGURATION & STYLING ---
SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"

st.set_page_config(
    page_title="Futsal Insta-Analytics PRO",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS für den "Pro-Look"
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #00CC96;
    }
    .stDataFrame {
        border: 1px solid #30363d;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATEN LADEN (VOLLSTÄNDIG) ---
@st.cache_data(ttl=3600)
def load_data_from_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        
        df_raw = pd.DataFrame(data)
        df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]
        
        if 'DATE' in df_raw.columns:
            df_raw['DATE'] = pd.to_datetime(df_raw['DATE']).dt.date
        
        df_raw['FOLLOWER'] = pd.to_numeric(df_raw['FOLLOWER'], errors='coerce').fillna(0)
        df_raw = df_raw.sort_values(by=['CLUB_NAME', 'DATE'])
        df_raw = df_raw.drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
        return df_raw
    except Exception as e:
        st.error(f"Daten-Fehler: {e}")
        return pd.DataFrame()

# --- 3. LOGIK & BERECHNUNGEN ---
df = load_data_from_sheets()

if not df.empty:
    # Aktuelle Daten pro Club
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
    
    # Trend-Berechnung (4 Wochen)
    latest_date_global = df['DATE'].max()
    target_date_4w = latest_date_global - timedelta(weeks=4)
    available_dates = sorted(df['DATE'].unique())
    closest_old_date = min(available_dates, key=lambda x: abs(x - target_date_4w))
    
    df_then = df[df['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
    df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
    df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
    
    # --- 4. DASHBOARD LAYOUT ---
    
    # Header
    col_logo, col_titel = st.columns([1, 4])
    with col_logo:
        # Falls das Logo nicht gefunden wird, nutzen wir ein Icon
        st.write("# ⚽") 
    with col_titel:
        st.title("Mister Futsal | Insta-Analytics")
        st.caption(f"Letztes Update: {latest_date_global.strftime('%d.%m.%Y')} | [misterfutsal.de](https://www.misterfutsal.de)")

    # Key Metrics (Die "Sammelkarten")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gesamt Follower", f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", "."), help="Summe aller getrackten Clubs")
    m2.metric("Top Club", df_latest.iloc[0]['CLUB_NAME'], f"{int(df_latest.iloc[0]['FOLLOWER']):,}".replace(",", "."))
    m3.metric("Clubs gesamt", len(df_latest))
    
    avg_growth = int(df_trend['Zuwachs'].mean())
    m4.metric("Ø Wachstum (4W)", f"+{avg_growth}")

    st.divider()

    # Main Content
    row1_left, row1_right = st.columns([1, 1], gap="large")

    with row1_left:
        st.subheader("🏆 Leaderboard")
        # Schicke Formatierung für das Leaderboard
        df_disp = df_latest.copy()
        df_disp.insert(0, 'RANG', range(1, len(df_disp) + 1))
        
        selection = st.dataframe(
            df_disp[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER']],
            column_config={
                "RANG": "Pos.",
                "CLUB_NAME": "Verein",
                "URL": st.column_config.LinkColumn("Instagram", display_text="Profil öffnen"),
                "FOLLOWER": st.column_config.NumberColumn("Follower", format="%d")
            },
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )

    with row1_right:
        st.subheader("🔍 Detail-Analyse")
        if selection and selection.selection.rows:
            sel_idx = selection.selection.rows[0]
            sel_club = df_disp.iloc[sel_idx]['CLUB_NAME']
            club_data = df[df['CLUB_NAME'] == sel_club].sort_values('DATE')
            
            fig_detail = px.area(club_data, x='DATE', y='FOLLOWER', 
                                title=f"Wachstum: {sel_club}",
                                color_discrete_sequence=['#00CC96'],
                                template="plotly_dark")
            fig_detail.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=350)
            st.plotly_chart(fig_detail, use_container_width=True)
        else:
            st.info("Klicke links auf einen Verein, um den zeitlichen Verlauf zu sehen.")

    st.divider()

    row2_left, row2_right = st.columns(2, gap="large")

    with row2_left:
        st.subheader("📈 Trend-Setter (Letzte 4 Wochen)")
        df_trend_top = df_trend.sort_values('Zuwachs', ascending=False).head(10)
        fig_trend = px.bar(df_trend_top, x='Zuwachs', y='CLUB_NAME', 
                          orientation='h',
                          title="Höchster Zuwachs",
                          color='Zuwachs',
                          color_continuous_scale='Viridis',
                          template="plotly_dark")
        fig_trend.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
        st.plotly_chart(fig_trend, use_container_width=True)

    with row2_right:
        st.subheader("🌐 Markt-Entwicklung")
        df_total_history = df.groupby('DATE')['FOLLOWER'].sum().reset_index()
        fig_total = px.line(df_total_history, x='DATE', y='FOLLOWER', 
                           title="Gesamt-Follower Futsal Deutschland",
                           template="plotly_dark",
                           color_discrete_sequence=['#FFB200'])
        fig_total.update_layout(height=400)
        st.plotly_chart(fig_total, use_container_width=True)

else:
    st.warning("Keine Daten gefunden. Bitte überprüfe die Google Sheets Verbindung.")
