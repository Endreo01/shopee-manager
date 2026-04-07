import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<p class="section-title">📢 Anúncios (Ads)</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Gerencie suas campanhas de anúncios na Shopee</p>', unsafe_allow_html=True)

    st.warning("⚠️ A API de Ads da Shopee requer permissão específica no app. Se aparecer erro de autorização, verifique as permissões do seu app no Open Platform.")

    if st.button("🔍 Carregar Campanhas"):
        with st.spinner("Buscando campanhas..."):
            result = sc.get_ads_campaigns()

        if result.get("error"):
            st.error(f"❌ Erro: {result['error']}")
            if result.get("details"):
                st.json(result["details"])
            return

        campaigns = result.get("response", {}).get("campaign_list", [])
        if not campaigns:
            st.info("Nenhuma campanha encontrada. Verifique se há campanhas ativas na sua conta.")
            st.json(result)
            return

        st.success(f"✅ {len(campaigns)} campanha(s) encontrada(s)")

        import pandas as pd
        rows = []
        for c in campaigns:
            rows.append({
                "ID": c.get("campaign_id"),
                "Nome": c.get("campaign_name", ""),
                "Status": c.get("campaign_status", ""),
                "Orçamento (R$)": c.get("campaign_budget", 0),
                "Tipo": c.get("campaign_type", ""),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Ativar / Pausar Campanha")

        campaign_names = [f"{c.get('campaign_id')} — {c.get('campaign_name', '')}" for c in campaigns]
        escolha = st.selectbox("Selecione a campanha", campaign_names)
        idx = campaign_names.index(escolha)
        campaign_id = campaigns[idx].get("campaign_id")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ Ativar", use_container_width=True):
                with st.spinner("Ativando..."):
                    res = sc.toggle_campaign(campaign_id, "RESUME")
                if res.get("error"):
                    st.error(f"❌ {res['error']}")
                else:
                    st.success("✅ Campanha ativada!")
        with col2:
            if st.button("⏸️ Pausar", use_container_width=True):
                with st.spinner("Pausando..."):
                    res = sc.toggle_campaign(campaign_id, "PAUSE")
                if res.get("error"):
                    st.error(f"❌ {res['error']}")
                else:
                    st.success("✅ Campanha pausada!")
