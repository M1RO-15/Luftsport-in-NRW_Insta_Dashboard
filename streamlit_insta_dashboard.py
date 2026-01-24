import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- Konfiguration ---
INSTA_SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"
ZUSCHAUER_SHEET_ID = "14puepYtteWGPD1Qv89gCpZijPm5Yrgr8glQnGBh3PXM"

st.set_page_config(page_title="Futsal Analytics Dashboard", layout="wide")

# --- Zentrale Funktion zum Laden der Daten ---
@st.cache_data(ttl=3600)
def load_data(sheet_id, secret_key):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets[secret_key]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        # Spaltennamen schön sauber machen (Großbuchstaben und ohne Leerzeichen)
        df.columns = [str(c).strip().upper() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden von {secret_key}: {e}")
        return pd.DataFrame()

# --- Haupt-Navigation (Die Reiter) ---
tab1, tab2 = st.tabs(["📸 Instagram Dashboard", "🏟️ Zuschauer Dashboard"])

# ==========================================
# REITER 1: INSTAGRAM
# ==========================================
with tab1:
    df = load_data(INSTA_SHEET_ID, "gcp_service_account")
    
    if not df.empty:
        # Daten vorbereiten
        if 'DATE' in df.columns:
            df['DATE'] = pd.to_datetime(df['DATE']).dt.date
        df['FOLLOWER'] = pd.to_numeric(df['FOLLOWER'], errors='coerce').fillna(0)
        df = df.sort_values(by=['CLUB_NAME', 'DATE'])
        df = df.drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')

        df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
        df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
        df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        
        df_latest_display = df_latest.copy()
        df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
        df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_latest_display['STAND'] = df_latest_display['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))

        akt_datum = df['DATE'].max().strftime('%d.%m.%Y')
        summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")

        # Layout
        st.image("logo_instagram_dashboard.png", width=350)
        st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
        st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")
        st.divider()

        col1, col2 = st.columns(2, gap="medium")
        with col1:
            st.subheader("🏆 Aktuelles Ranking")
            selection = st.dataframe(
                df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND']], 
                column_config={
                    "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"),
                },
                hide_index=True, on_select="rerun", selection_mode="multi-row", use_container_width=True, height=600
            )

        with col2:
            st.subheader("🔍 Detailanalyse")
            if selection and selection.selection.rows:
                sel_indices = selection.selection.rows
                sel_clubs = df_latest.iloc[sel_indices]['CLUB_NAME'].tolist()
                plot_data = df[df['CLUB_NAME'].isin(sel_clubs)]
                fig_detail = px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', markers=True)
                st.plotly_chart(fig_detail, use_container_width=True)
            else:
                st.info("💡 Klicke links auf Vereine für Details.")

# ==========================================
# REITER 2: ZUSCHAUER
# ==========================================
with tab2:
    st.header("🏟️ Zuschauer-Dashboard")
    df_z = load_data(ZUSCHAUER_SHEET_ID, "Google_Sheets_zuschauer")

    if not df_z.empty:
        # Datum umwandeln falls vorhanden
        if 'DATUM' in df_z.columns:
            df_z['DATUM'] = pd.to_datetime(df_z['DATUM']).dt.date
        
        # Sicherstellen, dass ZUSCHAUER eine Zahl ist
        if 'ZUSCHAUER' in df_z.columns:
            df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce').fillna(0)

        # Auswahl der Heim-Teams
        if 'HEIM' in df_z.columns:
            heim_teams = sorted(df_z['HEIM'].unique())
            auswahl_team = st.selectbox("Wähle einen Verein (Heimteam):", heim_teams)

            # Daten filtern für das ausgewählte Team
            team_data = df_z[df_z['HEIM'] == auswahl_team].sort_values('DATUM')

            if not team_data.empty:
                st.subheader(f"Zuschauer-Entwicklung: {auswahl_team}")
                fig_z = px.bar(
                    team_data, 
                    x='DATUM', 
                    y='ZUSCHAUER',
                    text='ZUSCHAUER',
                    color_discrete_sequence=['#00CC96'],
                    labels={'ZUSCHAUER': 'Anzahl Zuschauer', 'DATUM': 'Spieltag'}
                )
                fig_z.update_traces(textposition='outside')
                st.plotly_chart(fig_z, use_container_width=True)
            else:
                st.warning("Keine Daten für dieses Team gefunden.")
        else:
            st.error("Die Spalte 'HEIM' wurde im Sheet nicht gefunden.")
