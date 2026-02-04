# --- TAB 2: ZUSCHAUER ---
with tab_zuschauer:
    df_z = load_data(ZUSCHAUER_SHEET_ID, "gcp_service_account")
    df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce')
    df_z = df_z[df_z['ZUSCHAUER'] > 0]

    if not df_z.empty:
        if 'DATUM' in df_z.columns:
            df_z['DATUM'] = pd.to_datetime(df_z['DATUM'], dayfirst=True, errors='coerce')
        if 'ZUSCHAUER' in df_z.columns:
            df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce').fillna(0)
        if 'AVERAGE_SPIELTAG' in df_z.columns:
            df_z['AVERAGE_SPIELTAG'] = pd.to_numeric(df_z['AVERAGE_SPIELTAG'], errors='coerce').fillna(0)


        def get_season(d):
            if pd.isnull(d): return "Unbekannt"
            return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"


        if 'SAISON' not in df_z.columns and 'SEASON' in df_z.columns:
            df_z['SAISON'] = df_z['SEASON']
        elif 'SAISON' not in df_z.columns:
            df_z['SAISON'] = df_z['DATUM'].apply(get_season)

        unique_seasons = sorted([s for s in df_z['SAISON'].unique() if s != "Unbekannt"])
        color_map = {s: ('#0047AB' if i % 2 == 0 else '#FFC000') for i, s in enumerate(unique_seasons)}

        if 'HEIM' in df_z.columns:
            options_list = ["🇩🇪 Liga-Gesamtentwicklung (Spieltag-Schnitt)"] + sorted(df_z['HEIM'].unique())
            auswahl = st.selectbox("## Wähle einen Verein aus:", options_list, key="vereins_auswahl")

            if "Liga-Gesamtentwicklung" in auswahl:
                df_saison = df_z.groupby('SAISON')['ZUSCHAUER'].mean().reset_index()

                if not df_saison.empty:
                    farben_liste = ['#FFD700', '#0057B8']
                    df_saison['COLOR'] = [farben_liste[i % 2] for i in range(len(df_saison))]

                    fig_saison = px.bar(
                        df_saison,
                        x='SAISON',
                        y='ZUSCHAUER',
                        text='ZUSCHAUER',
                        title="Saisonschnitt Bundesliga gesamt",
                    )
                    fig_saison.update_traces(
                        marker_color=df_saison['COLOR'],
                        textposition='outside',
                        texttemplate='%{text:.0f}'
                    )
                    fig_saison.update_layout(
                        xaxis_title=None,
                        yaxis_title=None,
                        xaxis=dict(
                            tickfont=dict(size=10),
                            type='category'
                        ),
                        yaxis=dict(
                            range=[0, 350]
                        ),
                        hovermode="x unified"
                    )
                    st.plotly_chart(fig_saison, use_container_width=True)

                cols = ["DATUM", 'SAISON', 'SPIELTAG', 'AVERAGE_SPIELTAG']
                df_helper = df_z[[c for c in cols if c in df_z.columns]].copy()

                df_helper = df_helper.drop_duplicates(subset=['SAISON', 'SPIELTAG']).sort_values('DATUM')

                df_helper['DATUM'] = pd.to_datetime(df_helper['DATUM'])
                ist_doppelt = df_helper.duplicated(subset=['DATUM'], keep='first')
                df_helper.loc[ist_doppelt, 'DATUM'] = df_helper.loc[ist_doppelt, 'DATUM'] - pd.Timedelta(days=1)

                if not df_helper.empty:
                    fig_trend = px.bar(
                        df_helper,
                        x='DATUM',
                        y='AVERAGE_SPIELTAG',
                        color='SAISON',
                        text='AVERAGE_SPIELTAG',
                        title="Zuschauerschnitt im Saisonvergleich (nach Spieltag)",
                        color_discrete_sequence=['#FFD700', '#0057B8']
                    )

                    fig_trend.update_layout(
                        xaxis_title=None,
                        yaxis_title=None,
                        xaxis=dict(
                            type='category',
                            tickmode='array',
                            tickvals=df_helper['DATUM'],
                            ticktext=df_helper['SPIELTAG'],
                            tickangle=-45,
                            tickfont=dict(size=10)
                        ),
                        hovermode="x unified"
                    )

                    fig_trend.update_traces(textposition='outside')
                    st.plotly_chart(fig_trend, use_container_width=True)

                else:
                    st.warning("Die erforderlichen Spalten (SAISON, SPIELTAG, AVERAGE_SPIELTAG) fehlen im Datensatz.")

            else:
                team_data = df_z[df_z['HEIM'] == auswahl].sort_values('DATUM')
                st.markdown(f"### Entwicklung: {auswahl}")

                stats_saison = team_data.groupby('SAISON')['ZUSCHAUER'].mean().reset_index()
                stats_saison.columns = ['Saison', 'Ø Zuschauer']
                stats_saison['Ø Zuschauer'] = stats_saison['Ø Zuschauer'].round(0).astype(int)

                fig_avg = px.bar(stats_saison, x='Saison', y='Ø Zuschauer', text='Ø Zuschauer',
                                 title=f"Durchschnittliche Zuschauer pro Saison",
                                 color='Saison', color_discrete_map=color_map)
                fig_avg.update_traces(textposition='outside')
                fig_avg.update_layout(
                    xaxis=dict(fixedrange=True),
                    yaxis=dict(
                        fixedrange=True,
                        range=[0, stats_saison['Ø Zuschauer'].max() * 1.25],
                        nticks=10,
                        exponentformat="none"
                    ),
                    margin=dict(b=100)
                )
                st.plotly_chart(fig_avg, use_container_width=True)

                team_data['X_LABEL'] = team_data.apply(
                    lambda x: f"{x['DATUM'].strftime('%d.%m.%Y')} (ST {str(x['SPIELTAG']).replace('.0', '')})", axis=1)

                fig_team = px.bar(team_data, x='X_LABEL', y='ZUSCHAUER', text='ZUSCHAUER',
                                  color='SAISON', color_discrete_map=color_map,
                                  title=f"Alle Heimspiele von {auswahl}")

                fig_team.update_traces(textposition='outside')
                fig_team.update_layout(
                    xaxis=dict(fixedrange=True),
                    xaxis_tickangle=-45,
                    yaxis_range=[0, team_data['ZUSCHAUER'].max() * 1.25],
                    yaxis=dict(fixedrange=True, nticks=10, exponentformat="none"),
                    margin=dict(b=100)
                )

                st.plotly_chart(fig_team, use_container_width=True)
    else:
        st.error("Zuschauer-Daten konnten nicht geladen werden.")