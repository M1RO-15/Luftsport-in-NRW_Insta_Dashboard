import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- Konfiguration ---
SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"

st.set_page_config(
    page_title="Futsal Insta-Analytics", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Design-Optimierung (CSS) ---
st.markdown("""
    <style>
    .main { padding-top: 1rem; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #FFB200; }
    /* Macht die Titel auf Handys hübscher */
    @media (max-width: 640px) {
        .stTitle { font-size: 1.5rem !important; }
    }
    </style>
    """, unsafe_index=True)

@st.cache_data(ttl=3600)
def load_data_from_sheets():
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

try:
    df = load_data_from_sheets()

    # --- DATEN VORBEREITEN ---
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
    df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
    
    df_latest_display = df_latest.copy()
    df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
    df_latest_display['FOLLOWER_STR'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
    df_latest_display['STAND_STR'] = pd.to_datetime(df_latest_display['DATE']).dt.strftime('%d.%m.%Y')

    akt_datum = df['DATE'].max().strftime('%d.%m.%Y')
    summe_follower = int(df_latest['FOLLOWER'].sum())

    # --- KOPFZEILE ---
    header_col1, header_col2 = st.columns([1, 4])
    with header_col1:
        st.image("logo_instagram_dashboard.png", width=150)
    with header_col2:
        st.title("Mister Futsal - Instagram Dashboard")
        st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de)")

    # Wichtige Zahl als "Metric Box" (sieht auf Mobil super aus)
    st.metric(label=f"Gesamt-Follower (Stand {akt_datum})", value=f"{summe_follower:,}".replace(",", "."))
    st.divider()

    # --- OBERE REIHE ---
    row1_col1, row1_col2 = st.columns([1, 1])

    with row1_col1:
        st.subheader("🏆 Ranking")
        selection = st.dataframe(
            df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER_STR']],
            column_config={
                "RANG": st.column_config.TextColumn("Rang", width="small"),
                "URL": st.column_config.LinkColumn("Link", display_text="Profil"),
                "FOLLOWER_STR": st.column_config.TextColumn("Follower")
            },
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            height=400
        )

    with row1_col2:
        st.subheader("🔍 Analyse")
        if selection and selection.selection.rows:
            sel_idx = selection.selection.rows[0]
            sel_club = df_latest.iloc[sel_idx]['CLUB_NAME']
            club_data = df[df['CLUB_NAME'] == sel_club].sort_values('DATE')
            fig_detail = px.line(club_data, x='DATE', y='FOLLOWER', title=f"{sel_club}", markers=True, color_discrete_sequence=['#00CC96'])
            fig_detail.update_layout(margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_detail, use_container_width=True)
        else:
            st.info("Klicke links auf einen Verein!")

    st.divider()

    # --- UNTERE REIHE ---
    row2_col1, row2_col2 = st.columns([1, 1])

    with row2_col1:
        st.subheader("📈 Trend")
        target_date_4w = df['DATE'].max() - timedelta(weeks=4)
        available_dates = sorted(df['DATE'].unique())
        closest_old_date = min(available_dates, key=lambda x: abs(x - target_date_4w))
        
        df_then = df[df['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
        df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
        df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
        df_trend = df_trend.sort_values(by='Zuwachs', ascending=False)
        
        df_trend['RANG'] = range(1, len(df_trend) + 1)
        df_trend['RANG'] = df_trend['RANG'].astype(str)
        df_trend['Zuwachs_STR'] = df_trend['Zuwachs'].apply(lambda x: f"+{int(x)}" if x > 0 else str(int(x)))

        st.dataframe(
            df_trend[['RANG', 'CLUB_NAME', 'Zuwachs_STR']],
            column_config={
                "RANG": st.column_config.TextColumn("Rang", width="small"),
                "Zuwachs_STR": st.column_config.TextColumn("Zuwachs")
            },
            hide_index=True,
            use_container_width=True,
            height=400
        )

    with row2_col2:
        st.subheader("🌐 Deutschland")
        df_total_history = df.groupby('DATE')['FOLLOWER'].sum().reset_index()
        fig_total = px.line(df_total_history, x='DATE', y='FOLLOWER', markers=True, color_discrete_sequence=['#FFB200'])
        fig_total.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_total, use_container_width=True)

except Exception as e:
    st.error(f"Oje, ein Fehler: {e}")
