import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- KONFIGURATION & DESIGN ---
SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"

st.set_page_config(
    page_title="Mister Futsal Analytics",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS für professionelles Look & Feel (Desktop & Mobil)
st.markdown("""
    <style>
    /* Hintergrund und Abstände */
    .main { background-color: #0e1117; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    /* Header Styling */
    .header-container {
        display: flex;
        align-items: center;
        gap: 20px;
        margin-bottom: 1rem;
    }
    
    /* Responsive Anpassung für Mobilgeräte */
    @media (max-width: 768px) {
        .header-container {
            flex-direction: column;
            text-align: center;
        }
        .stMetric { text-align: center; }
    }

    /* Metric Box Verschönerung */
    div[data-testid="stMetric"] {
        background-color: #1e2130;
        border: 1px solid #31333f;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Linksbündige Tabellen-Texte */
    .stDataFrame div[data-testid="stTable"] td {
        text-align: left !important;
    }
    
    /* Link Styling */
    .futsal-link {
        color: #FFB200;
        text-decoration: none;
        font-weight: bold;
        font-size: 1.1rem;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_data_from_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().upper() for c in df.columns]
        if 'DATE' in df.columns:
            df['DATE'] = pd.to_datetime(df['DATE']).dt.date
        df['FOLLOWER'] = pd.to_numeric(df['FOLLOWER'], errors='coerce').fillna(0)
        df = df.sort_values(by=['CLUB_NAME', 'DATE'])
        df = df.drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
        return df
    except Exception as e:
        st.error(f"Datenverbindung fehlgeschlagen: {e}")
        return pd.DataFrame()

# --- APP LOGIK ---
df = load_data_from_sheets()

if not df.empty:
    # --- DATENAUFBEREITUNG ---
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
    df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
    
    akt_datum = df['DATE'].max().strftime('%d.%m.%Y')
    summe_follower = int(df_latest['FOLLOWER'].sum())

    # --- HEADER BEREICH ---
    # Container für Logo und Titel
    with st.container():
        col_img, col_txt = st.columns([1, 4])
        with col_img:
            st.image("logo_instagram_dashboard.png", use_container_width=True)
        with col_txt:
            st.title("Mister Futsal - Instagram Dashboard")
            st.markdown(f'<a href="https://www.misterfutsal.de" class="futsal-link">www.misterfutsal.de</a>', unsafe_allow_html=True)
            st.metric(label=f"Gesamt-Follower (Stand {akt_datum})", value=f"{summe_follower:,}".replace(",", "."))

    st.divider()

    # --- MAIN DASHBOARD (ZWEI SPALTEN) ---
    row1_left, row1_right = st.columns([1, 1], gap="large")

    with row1_left:
        st.subheader("🏆 Aktuelles Ranking")
        # Aufbereitung für linksbündige Anzeige
        df_rank_display = df_latest.copy()
        df_rank_display['RANG'] = df_rank_display['RANG'].astype(str)
        df_rank_display['FOLLOWER_STR'] = df_rank_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        
        selection = st.dataframe(
            df_rank_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER_STR']],
            column_config={
                "RANG": st.column_config.TextColumn("Rang", width="small"),
                "CLUB_NAME": st.column_config.TextColumn("Verein"),
                "URL": st.column_config.LinkColumn("Instagram", display_text="Profil"),
                "FOLLOWER_STR": st.column_config.TextColumn("Follower")
            },
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            height=450
        )

    with row1_right:
        st.subheader("🔍 Detailanalyse")
        if selection and selection.selection.rows:
            sel_idx = selection.selection.rows[0]
            sel_club = df_latest.iloc[sel_idx]['CLUB_NAME']
            club_data = df[df['CLUB_NAME'] == sel_club].sort_values('DATE')
            
            fig_detail = px.line(
                club_data, x='DATE', y='FOLLOWER', 
                title=f"Wachstum: {sel_club}", 
                markers=True, 
                color_discrete_sequence=['#00CC96']
            )
            fig_detail.update_layout(hovermode="x unified", template="plotly_dark")
            st.plotly_chart(fig_detail, use_container_width=True)
        else:
            st.info("💡 Wähle einen Verein in der Tabelle aus, um den Verlauf zu sehen.")

    st.divider()

    # --- TRENDS & GESAMTENTWICKLUNG ---
    row2_left, row2_right = st.columns([1, 1], gap="large")

    with row2_left:
        st.subheader("📈 Top-Gewinner (Trend)")
        # Trendberechnung (4 Wochen)
        target_date = df['DATE'].max() - timedelta(weeks=4)
        available_dates = sorted(df['DATE'].unique())
        closest_date = min(available_dates, key=lambda x: abs(x - target_date))
        
        df_then = df[df['DATE'] == closest_date][['CLUB_NAME', 'FOLLOWER']]
        df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
        df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
        df_trend = df_trend.sort_values(by='Zuwachs', ascending=False)
        
        # Formatierung
        df_trend['Zuwachs_STR'] = df_trend['Zuwachs'].apply(lambda x: f"+{int(x)}" if x > 0 else str(int(x)))
        
        st.dataframe(
            df_trend[['CLUB_NAME', 'Zuwachs_STR']],
            column_config={
                "CLUB_NAME": st.column_config.TextColumn("Verein"),
                "Zuwachs_STR": st.column_config.TextColumn("Zuwachs (4 Wo.)")
            },
            hide_index=True,
            use_container_width=True,
            height=400
        )

    with row2_right:
        st.subheader("🌐 Gesamtentwicklung DE")
        df_total = df.groupby('DATE')['FOLLOWER'].sum().reset_index()
        fig_total = px.area(
            df_total, x='DATE', y='FOLLOWER', 
            title="Summe aller Follower",
            color_discrete_sequence=['#FFB200']
        )
        fig_total.update_layout(template="plotly_dark")
        st.plotly_chart(fig_total, use_container_width=True)

else:
    st.warning("Keine Daten gefunden. Bitte prüfe die Google Sheet Anbindung.")
