"""
app.py
──────
Dashboard Streamlit — Finance BigData
Données depuis PostgreSQL Data Warehouse
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from datetime import datetime

# ── Config page ───────────────────────────────────────────
st.set_page_config(
    page_title="Finance BigData Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Config PostgreSQL ─────────────────────────────────────
DW_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "finance_dw",
    "user":     "dw_user",
    "password": "dw_password",
}


# ── Connexion DW ──────────────────────────────────────────
@st.cache_resource
def get_conn():
    return psycopg2.connect(**DW_CONFIG)


@st.cache_data(ttl=300)
def query(sql: str) -> pd.DataFrame:
    conn = psycopg2.connect(**DW_CONFIG)
    df   = pd.read_sql(sql, conn)
    conn.close()
    return df


# ════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2910/2910768.png", width=80)
st.sidebar.title("Finance BigData")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Snapshot Marché",
     "📈 Prix & Variations",
     "🏆 Top Mouvements",
     "🪙 Cryptomonnaies",
     "🚨 Alertes Prix",
     "🗄️ Historique"]
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Mise à jour :** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.sidebar.markdown("**Sources :** Yahoo · Binance · CoinGecko · Boursorama")


# ════════════════════════════════════════════════════════════
#  PAGE 1 : SNAPSHOT MARCHÉ
# ════════════════════════════════════════════════════════════
if page == "📊 Snapshot Marché":
    st.title("📊 Snapshot Global du Marché")

    df_snap = query("SELECT * FROM snapshot_marche ORDER BY inserted_at DESC LIMIT 1")

    if df_snap.empty:
        st.warning("Aucune donnée disponible")
    else:
        row = df_snap.iloc[0]

        # KPI Cards
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Actifs",      int(row["total_actifs"]))
        col2.metric("En Hausse 📈",      int(row["actifs_en_hausse"]),
                    f"{row['pct_marche_hausse']}%")
        col3.metric("En Baisse 📉",      int(row["actifs_en_baisse"]))
        col4.metric("Variation Moyenne", f"{row['variation_moyenne']:.2f}%")
        col5.metric("Variation Médiane", f"{row['variation_mediane']:.2f}%")

        st.markdown("---")

        # Jauge sentiment marché
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Sentiment du marché")
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=float(row["pct_marche_hausse"]),
                title={"text": "% Actifs en hausse"},
                delta={"reference": 50},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar":  {"color": "#2ecc71"},
                    "steps": [
                        {"range": [0,  40], "color": "#e74c3c"},
                        {"range": [40, 60], "color": "#f39c12"},
                        {"range": [60, 100],"color": "#2ecc71"},
                    ],
                    "threshold": {
                        "line":  {"color": "black", "width": 4},
                        "thickness": 0.75,
                        "value": 50
                    }
                }
            ))
            fig_gauge.update_layout(height=300)
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_b:
            st.subheader("Répartition hausse / baisse")
            fig_pie = px.pie(
                values=[
                    int(row["actifs_en_hausse"]),
                    int(row["actifs_en_baisse"]),
                    int(row["actifs_neutres"]) if row["actifs_neutres"] else 0
                ],
                names=["Hausse", "Baisse", "Neutre"],
                color_discrete_sequence=["#2ecc71", "#e74c3c", "#95a5a6"],
                hole=0.4
            )
            fig_pie.update_layout(height=300)
            st.plotly_chart(fig_pie, use_container_width=True)

        # Résumé par catégorie
        st.subheader("Résumé par catégorie")
        df_cat = query("""
            SELECT categorie, nb_actifs, variation_moyenne,
                   nb_en_hausse, nb_en_baisse, volume_total
            FROM resume_categorie
            ORDER BY nb_actifs DESC
        """)
        if not df_cat.empty:
            fig_bar = px.bar(
                df_cat,
                x="categorie",
                y="variation_moyenne",
                color="variation_moyenne",
                color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                title="Variation moyenne par catégorie (%)",
                text="variation_moyenne"
            )
            fig_bar.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            fig_bar.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

            st.dataframe(
                df_cat.style.format({
                    "variation_moyenne": "{:.2f}%",
                    "volume_total": "{:,.0f}"
                }),
                use_container_width=True
            )


# ════════════════════════════════════════════════════════════
#  PAGE 2 : PRIX & VARIATIONS
# ════════════════════════════════════════════════════════════
elif page == "📈 Prix & Variations":
    st.title("📈 Prix & Variations")

    # Filtre catégorie
    categories = ["Toutes", "action", "action_fr", "crypto", "indice"]
    cat_choisie = st.selectbox("Filtrer par catégorie", categories)

    if cat_choisie == "Toutes":
        df = query("SELECT * FROM historique_prix ORDER BY variation_pct DESC")
    else:
        df = query(f"""
            SELECT * FROM historique_prix
            WHERE categorie = '{cat_choisie}'
            ORDER BY variation_pct DESC
        """)

    if df.empty:
        st.warning("Aucune donnée")
    else:
        # Scatter prix vs variation
        st.subheader("Prix vs Variation (%)")
        fig_scatter = px.scatter(
            df,
            x="variation_pct",
            y="prix",
            color="categorie",
            size_max=20,
            hover_data=["ticker", "nom", "devise", "source"],
            color_discrete_sequence=px.colors.qualitative.Set2,
            title="Prix actuel vs Variation journalière",
            text="ticker"
        )
        fig_scatter.update_traces(textposition="top center", textfont_size=9)
        fig_scatter.add_vline(x=0, line_dash="dash", line_color="gray")
        fig_scatter.update_layout(height=500)
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Tableau
        st.subheader("Tableau des actifs")
        cols_affich = ["ticker", "nom", "prix", "variation_pct",
                       "prix_haut", "prix_bas", "volume", "devise",
                       "categorie", "source"]
        cols_ok = [c for c in cols_affich if c in df.columns]

        def couleur_variation(val):
            if pd.isna(val):
                return ""
            return "color: green" if val > 0 else "color: red"

        st.dataframe(
            df[cols_ok].style
            .applymap(couleur_variation, subset=["variation_pct"])
            .format({
                "prix":          "{:.4f}",
                "variation_pct": "{:+.2f}%",
                "prix_haut":     "{:.4f}",
                "prix_bas":      "{:.4f}",
                "volume":        "{:,.0f}",
            }, na_rep="—"),
            use_container_width=True,
            height=400
        )


# ════════════════════════════════════════════════════════════
#  PAGE 3 : TOP MOUVEMENTS
# ════════════════════════════════════════════════════════════
elif page == "🏆 Top Mouvements":
    st.title("🏆 Top Mouvements")

    df_top = query("""
        SELECT * FROM top_mouvements
        ORDER BY variation_pct DESC
    """)

    if df_top.empty:
        st.warning("Aucune donnée")
    else:
        col1, col2 = st.columns(2)

        hausses = df_top[df_top["type_mouvement"] == "hausse"]
        baisses = df_top[df_top["type_mouvement"] == "baisse"]

        with col1:
            st.subheader("🟢 Top Hausses")
            fig_h = px.bar(
                hausses.sort_values("variation_pct", ascending=True),
                x="variation_pct",
                y="ticker",
                orientation="h",
                color="variation_pct",
                color_continuous_scale=["#a8edba", "#2ecc71"],
                text="variation_pct",
                title="Meilleures performances"
            )
            fig_h.update_traces(texttemplate="%{text:+.2f}%", textposition="outside")
            fig_h.update_layout(height=350, showlegend=False,
                                coloraxis_showscale=False)
            st.plotly_chart(fig_h, use_container_width=True)

        with col2:
            st.subheader("🔴 Top Baisses")
            fig_b = px.bar(
                baisses.sort_values("variation_pct", ascending=False),
                x="variation_pct",
                y="ticker",
                orientation="h",
                color="variation_pct",
                color_continuous_scale=["#e74c3c", "#fadbd8"],
                text="variation_pct",
                title="Moins bonnes performances"
            )
            fig_b.update_traces(texttemplate="%{text:+.2f}%", textposition="outside")
            fig_b.update_layout(height=350, showlegend=False,
                                coloraxis_showscale=False)
            st.plotly_chart(fig_b, use_container_width=True)

        # Résumé par devise
        st.subheader("Résumé par devise")
        df_devise = query("SELECT * FROM resume_devise ORDER BY nb_actifs DESC")
        if not df_devise.empty:
            fig_devise = px.bar(
                df_devise,
                x="devise",
                y=["nb_en_hausse", "nb_en_baisse"],
                barmode="group",
                color_discrete_map={
                    "nb_en_hausse": "#2ecc71",
                    "nb_en_baisse": "#e74c3c"
                },
                title="Actifs en hausse/baisse par devise"
            )
            fig_devise.update_layout(height=300)
            st.plotly_chart(fig_devise, use_container_width=True)


# ════════════════════════════════════════════════════════════
#  PAGE 4 : CRYPTOMONNAIES
# ════════════════════════════════════════════════════════════
elif page == "🪙 Cryptomonnaies":
    st.title("🪙 Cryptomonnaies")

    df_crypto = query("""
        SELECT * FROM top_cryptos_cap
        ORDER BY capitalisation DESC
    """)

    if df_crypto.empty:
        st.warning("Aucune donnée crypto")
    else:
        # KPIs
        col1, col2, col3 = st.columns(3)
        col1.metric("Cryptos suivies", len(df_crypto))
        col2.metric("Cap. totale",
                    f"${df_crypto['capitalisation'].sum()/1e12:.2f}T")
        col3.metric("Volume total 24h",
                    f"${df_crypto['volume'].sum()/1e9:.1f}B")

        st.markdown("---")

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Capitalisation boursière")
            fig_cap = px.treemap(
                df_crypto,
                path=["ticker"],
                values="capitalisation",
                color="variation_pct",
                color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                title="Taille = capitalisation · Couleur = variation"
            )
            fig_cap.update_layout(height=400)
            st.plotly_chart(fig_cap, use_container_width=True)

        with col_b:
            st.subheader("Volume échangé 24h")
            fig_vol = px.bar(
                df_crypto.sort_values("volume", ascending=True),
                x="volume",
                y="ticker",
                orientation="h",
                color="variation_pct",
                color_continuous_scale=["#e74c3c", "#2ecc71"],
                title="Volume 24h par crypto"
            )
            fig_vol.update_layout(height=400, coloraxis_showscale=False)
            st.plotly_chart(fig_vol, use_container_width=True)

        # Tableau détaillé
        st.subheader("Détail des cryptos")
        st.dataframe(
            df_crypto.style.format({
                "prix":           "${:.2f}",
                "capitalisation": "${:,.0f}",
                "volume":         "${:,.0f}",
                "variation_pct":  "{:+.2f}%",
            }, na_rep="—"),
            use_container_width=True
        )


# ════════════════════════════════════════════════════════════
#  PAGE 5 : ALERTES PRIX
# ════════════════════════════════════════════════════════════
elif page == "🚨 Alertes Prix":
    st.title("🚨 Alertes Prix")

    df_alertes = query("""
        SELECT * FROM alertes_prix
        ORDER BY variation_pct DESC
    """)

    if df_alertes.empty:
        st.success("✅ Aucune alerte — tous les actifs dans les limites normales")
    else:
        st.warning(f"⚠️ {len(df_alertes)} actifs avec variation > 2%")

        for _, row in df_alertes.iterrows():
            couleur = "🟢" if row["variation_pct"] > 0 else "🔴"
            with st.expander(
                f"{couleur} {row['ticker']} — {row['variation_pct']:+.2f}% "
                f"({row['niveau_alerte']})"
            ):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Prix actuel", f"{row['prix']:.4f} {row['devise']}")
                col2.metric("Variation",   f"{row['variation_pct']:+.2f}%")
                col3.metric("Catégorie",   row["categorie"])
                col4.metric("Source",      row["source"])

        # Graphique alertes
        fig_alerte = px.bar(
            df_alertes.sort_values("variation_pct"),
            x="ticker",
            y="variation_pct",
            color="niveau_alerte",
            color_discrete_map={
                "forte hausse": "#2ecc71",
                "forte baisse": "#e74c3c"
            },
            title="Actifs en alerte",
            text="variation_pct"
        )
        fig_alerte.update_traces(texttemplate="%{text:+.2f}%", textposition="outside")
        fig_alerte.add_hline(y=2,   line_dash="dash", line_color="green")
        fig_alerte.add_hline(y=-2,  line_dash="dash", line_color="red")
        fig_alerte.update_layout(height=400)
        st.plotly_chart(fig_alerte, use_container_width=True)


# ════════════════════════════════════════════════════════════
#  PAGE 6 : HISTORIQUE
# ════════════════════════════════════════════════════════════
elif page == "🗄️ Historique":
    st.title("🗄️ Historique des Prix")

    # Filtre ticker
    df_tickers = query("SELECT DISTINCT ticker FROM historique_prix ORDER BY ticker")
    tickers    = df_tickers["ticker"].tolist()
    ticker_choisi = st.selectbox("Choisir un actif", tickers)

    df_hist = query(f"""
        SELECT ticker, prix, variation_pct, volume,
               date_collecte, categorie, source, inserted_at
        FROM historique_prix
        WHERE ticker = '{ticker_choisi}'
        ORDER BY inserted_at DESC
    """)

    if df_hist.empty:
        st.warning("Aucune donnée pour cet actif")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Prix actuel",  f"{df_hist.iloc[0]['prix']:.4f}")
        col2.metric("Variation",    f"{df_hist.iloc[0]['variation_pct']:+.2f}%")
        col3.metric("Nb entrées",   len(df_hist))

        st.subheader(f"Évolution du prix — {ticker_choisi}")
        if len(df_hist) > 1:
            fig_line = px.line(
                df_hist.sort_values("inserted_at"),
                x="inserted_at",
                y="prix",
                title=f"Prix historique de {ticker_choisi}",
                markers=True
            )
            fig_line.update_layout(height=400)
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Une seule entrée disponible — relance le pipeline pour enrichir l'historique")

        st.subheader("Données brutes")
        st.dataframe(
            df_hist.style.format({
                "prix":          "{:.4f}",
                "variation_pct": "{:+.2f}%",
                "volume":        "{:,.0f}",
            }, na_rep="—"),
            use_container_width=True,
            height=300
        )