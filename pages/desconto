import streamlit as st
import shopee_client as sc
import supabase_client as sdb
import pandas as pd


def render():
    st.markdown('<p class="section-title">🏷️ Desconto do Vendedor</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Crie e gerencie descontos diretos nos seus produtos</p>', unsafe_allow_html=True)

    st.info("O desconto do vendedor é aplicado diretamente no produto como preço promocional. O preço original (DE) é mantido e o cliente vê o preço com desconto.")

    # ── Carregar produtos ─────────────────────────────────────────────────────
    col_db, col_api, _ = st.columns([1.5, 1.5, 3])
    with col_db:
        btn_db = st.button("⚡ Carregar do Banco", use_container_width=True)
    with col_api:
        btn_api = st.button("🔄 Buscar da API", use_container_width=True)

    if btn_db:
        with st.spinner("Carregando do banco..."):
            df = sdb.carregar_produtos_db()
        if df.empty:
            st.warning("Banco vazio. Use **Buscar da API**.")
            st.stop()
        df = df[df["Status"] == "NORMAL"]
        st.session_state["desconto_df"] = df
        st.success(f"✅ {len(df):,} produtos carregados!")

    if btn_api:
        with st.spinner("Buscando produtos..."):
            result = sc.get_item_list(offset=0, page_size=50, status="NORMAL")
        items = result.get("response", {}).get("item", [])
        if not items:
            st.warning("Nenhum produto encontrado.")
            st.stop()
        ids = [i["item_id"] for i in items]
        with st.spinner("Carregando detalhes..."):
            detail = sc.get_item_base_info(ids)
        detail_items = detail.get("response", {}).get("item_list", [])
        rows = []
        for it in detail_items:
            pi = it.get("price_info", [{}])
            preco = pi[0].get("current_price", 0) if pi else 0
            rows.append({
                "ID":         it.get("item_id"),
                "Nome":       it.get("item_name",""),
                "SKU":        it.get("item_sku",""),
                "Preco (R$)": float(preco),
                "Status":     it.get("item_status",""),
            })
        st.session_state["desconto_df"] = pd.DataFrame(rows)
        st.success(f"✅ {len(rows)} produtos carregados!")

    if st.session_state.get("desconto_df") is None:
        st.info("👆 Carregue os produtos primeiro.")
        st.stop()

    df = st.session_state["desconto_df"]

    st.divider()
    st.markdown("### 🔍 Selecionar Produto")

    col_tipo, col_busca = st.columns([1.2, 3])
    with col_tipo:
        tipo = st.selectbox("Buscar por", ["Nome", "SKU", "ID"])
    with col_busca:
        termo = st.text_input("Termo", placeholder="Use ; para múltiplos")

    df_fil = df.copy()
    if termo.strip():
        termos = [t.strip() for t in termo.split(";") if t.strip()]
        if tipo == "Nome":
            mask = pd.Series([False]*len(df_fil), index=df_fil.index)
            for t in termos:
                mask |= df_fil["Nome"].str.contains(t, case=False, na=False)
            df_fil = df_fil[mask]
        elif tipo == "SKU":
            mask = pd.Series([False]*len(df_fil), index=df_fil.index)
            for t in termos:
                mask |= df_fil["SKU"].str.contains(t, case=False, na=False)
            df_fil = df_fil[mask]
        elif tipo == "ID":
            ids = [int(x) for x in termo.replace(";",",").split(",") if x.strip().isdigit()]
            df_fil = df_fil[df_fil["ID"].isin(ids)]

    if df_fil.empty:
        st.info("Nenhum produto encontrado.")
        st.stop()

    st.dataframe(df_fil[["ID","Nome","SKU","Preco (R$)"]],
                 use_container_width=True, hide_index=True,
                 column_config={"Preco (R$)": st.column_config.NumberColumn(format="R$ %.2f")})

    st.divider()
    st.markdown("### 💸 Aplicar Desconto")

    tab_individual, tab_massa = st.tabs(["Individual", "Em Massa"])

    # ── Individual ────────────────────────────────────────────────────────────
    with tab_individual:
        nomes = [f"{r['ID']} — {r['Nome'][:60]}" for _, r in df_fil.iterrows()]
        escolha = st.selectbox("Selecione o produto", nomes)
        idx   = nomes.index(escolha)
        item  = df_fil.iloc[idx]
        preco_atual = float(item["Preco (R$)"])

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            tipo_desc = st.selectbox("Tipo de desconto", ["Percentual (%)", "Valor fixo (R$)"])
        with col_b:
            if tipo_desc == "Percentual (%)":
                pct = st.number_input("Desconto (%)", min_value=1.0, max_value=99.0, value=10.0, step=0.5)
                novo_preco = round(preco_atual * (1 - pct/100), 2)
            else:
                desconto = st.number_input("Desconto (R$)", min_value=0.01, value=5.0, step=0.01)
                novo_preco = round(max(preco_atual - desconto, 0.01), 2)
        with col_c:
            st.metric("Preço atual", f"R$ {preco_atual:.2f}")

        st.metric("Novo preço com desconto", f"R$ {novo_preco:.2f}",
                  delta=f"-R$ {preco_atual - novo_preco:.2f}")

        if st.button("✅ Aplicar Desconto", type="primary"):
            with st.spinner("Aplicando..."):
                res = sc.update_price(item["ID"], model_id=0, price=novo_preco)
            if res.get("error"):
                st.error(f"❌ {res['error']}")
            else:
                st.success(f"✅ Desconto aplicado! Novo preço: R$ {novo_preco:.2f}")

    # ── Em Massa ──────────────────────────────────────────────────────────────
    with tab_massa:
        st.info(f"Aplicará desconto em todos os **{len(df_fil)}** produtos filtrados.")

        col_a, col_b = st.columns(2)
        with col_a:
            tipo_desc_m = st.selectbox("Tipo", ["Percentual (%)", "Valor fixo (R$)"], key="desc_massa_tipo")
        with col_b:
            if tipo_desc_m == "Percentual (%)":
                pct_m = st.number_input("Desconto (%)", 1.0, 99.0, 10.0, 0.5, key="desc_massa_pct")
            else:
                val_m = st.number_input("Desconto (R$)", 0.01, value=5.0, step=0.01, key="desc_massa_val")

        if st.button("🚀 Aplicar em Todos os Filtrados", type="primary"):
            erros = []
            prog  = st.progress(0, text="Aplicando descontos...")
            total = len(df_fil)
            for i, (_, row) in enumerate(df_fil.iterrows()):
                preco = float(row["Preco (R$)"])
                if tipo_desc_m == "Percentual (%)":
                    novo = round(preco * (1 - pct_m/100), 2)
                else:
                    novo = round(max(preco - val_m, 0.01), 2)
                res = sc.update_price(row["ID"], model_id=0, price=novo)
                if res.get("error"):
                    erros.append(f"{row['SKU']}: {res['error']}")
                prog.progress((i+1)/total, text=f"Atualizando {i+1} de {total}...")
            prog.empty()
            if erros:
                st.warning(f"⚠️ {len(erros)} erro(s):")
                for e in erros:
                    st.caption(e)
            else:
                st.success(f"✅ Desconto aplicado em {total} produto(s)!")

        st.caption("⚠️ Esta ação altera o preço de todos os produtos visíveis no filtro acima.")