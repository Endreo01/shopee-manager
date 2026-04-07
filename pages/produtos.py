import streamlit as st
import shopee_client as sc
import pandas as pd


def render():
    st.markdown('<p class="section-title">🛍️ Produtos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Listagem e busca de produtos da sua loja Shopee</p>', unsafe_allow_html=True)

    # ── Filtros / Busca ───────────────────────────────────────────────────────
    col_status, col_tipo, col_busca = st.columns([1, 1.2, 2.5])

    with col_status:
        status = st.selectbox("Status", ["NORMAL", "BANNED", "DELETED", "UNLIST"], index=0)

    with col_tipo:
        tipo_busca = st.selectbox(
            "Buscar por",
            ["Nome", "SKU do Vendedor", "ID da Shopee"],
            index=0,
        )

    with col_busca:
        placeholder_map = {
            "Nome":            "Digite parte do nome...",
            "SKU do Vendedor": "Ex: SKU-001",
            "ID da Shopee":    "Ex: 123456789  (separe por vírgula para buscar vários)",
        }
        busca = st.text_input(
            "Buscar",
            placeholder=placeholder_map[tipo_busca],
            label_visibility="collapsed",
        )

    carregar_todos = st.checkbox(
        "Carregar todos os produtos (pode demorar para catálogos grandes)",
        value=False,
    )

    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
    with col_btn1:
        btn_carregar = st.button("🔍 Carregar / Buscar", type="primary", use_container_width=True)
    with col_btn2:
        btn_limpar = st.button("🗑 Limpar", use_container_width=True)

    if btn_limpar:
        st.session_state.pop("produtos_df", None)
        st.rerun()

    # ── Lógica de busca ───────────────────────────────────────────────────────
    if btn_carregar:
        item_ids = []

        # ── ROTA 1: Busca por ID direto ───────────────────────────────────────
        if tipo_busca == "ID da Shopee" and busca.strip():
            raw_ids = [x.strip() for x in busca.replace(",", " ").split() if x.strip().isdigit()]
            if not raw_ids:
                st.error("❌ ID inválido. Digite apenas números (separe múltiplos por vírgula).")
                return
            item_ids = [int(i) for i in raw_ids]

        # ── ROTA 2: Busca por SKU via search_item ─────────────────────────────
        elif tipo_busca == "SKU do Vendedor" and busca.strip():
            with st.spinner("Buscando produto pelo SKU..."):
                res = sc.search_item(busca.strip(), search_by="sku")
                if res.get("error"):
                    st.error(f"❌ Erro: {res['error']}")
                    return
                id_list = res.get("response", {}).get("item_id_list", [])
                if not id_list:
                    st.info(f"Nenhum produto encontrado com o SKU **{busca}**.")
                    return
                item_ids = [i["item_id"] for i in id_list]

        # ── ROTA 3: Lista normal (com filtro de nome opcional) ────────────────
        else:
            all_items = []
            offset = 0
            page_size = 100

            with st.spinner("Buscando lista de produtos..."):
                progress = st.progress(0, text="Carregando página 1...")
                while True:
                    result = sc.get_item_list(offset=offset, page_size=page_size, status=status)

                    if result.get("error"):
                        st.error(f"❌ Erro: {result['error']}")
                        return

                    response = result.get("response", {})
                    items = response.get("item", [])
                    all_items.extend(items)

                    total_count = response.get("total_count", len(all_items))
                    has_next = response.get("has_next_page", False)

                    progress.progress(
                        min(len(all_items) / max(total_count, 1), 1.0),
                        text=f"Lista: {len(all_items)} de {total_count} produtos...",
                    )

                    if not has_next or not carregar_todos:
                        break
                    offset += page_size

                progress.empty()

            if not all_items:
                st.info("Nenhum produto encontrado.")
                return

            item_ids = [i["item_id"] for i in all_items]

        # ── Busca base info em lotes de 50 ────────────────────────────────────
        detail_items = []
        with st.spinner(f"Carregando informações de {len(item_ids)} produto(s)..."):
            p2 = st.progress(0, text="Base info...")
            for i in range(0, len(item_ids), 50):
                batch = item_ids[i:i + 50]
                res = sc.get_item_base_info(batch)
                detail_items.extend(res.get("response", {}).get("item_list", []))
                p2.progress(min((i + 50) / len(item_ids), 1.0))
            p2.empty()

        # ── Busca extra info em lotes de 50 ───────────────────────────────────
        # Campos corretos da API: view_count, sold_count, liked_count, conversion_rate
        extra_map = {}
        with st.spinner("Carregando dados de performance..."):
            p3 = st.progress(0, text="Performance...")
            for i in range(0, len(item_ids), 50):
                batch = item_ids[i:i + 50]
                res = sc.get_item_extra_info(batch)
                # A API retorna "item_extra_info_list" (não "item_list")
                for ei in res.get("response", {}).get("item_extra_info_list", []):
                    extra_map[ei.get("item_id")] = ei
                p3.progress(min((i + 50) / len(item_ids), 1.0))
            p3.empty()

        # ── Monta DataFrame ───────────────────────────────────────────────────
        rows = []
        for item in detail_items:
            item_id = item.get("item_id")
            extra = extra_map.get(item_id, {})

            # Estoque
            stock_info = item.get("stock_info_v2", {})
            seller_stock_list = stock_info.get("seller_stock", [])
            seller_stock = seller_stock_list[0].get("stock", 0) if seller_stock_list else 0
            shopee_stock_list = stock_info.get("shopee_stock", [])
            shopee_stock = shopee_stock_list[0].get("stock", 0) if shopee_stock_list else 0

            # Preço
            price_info = item.get("price_info", [{}])
            preco = (price_info[0].get("current_price", 0) / 100_000) if price_info else 0

            # Performance — nomes corretos da API Shopee
            views    = extra.get("view_count", 0) or 0
            sold     = extra.get("sold_count", 0) or 0
            likes    = extra.get("liked_count", 0) or 0
            conv_raw = extra.get("conversion_rate", 0) or 0
            # conversion_rate já vem como decimal (ex: 0.05 = 5%). Se vier como inteiro, ajusta.
            conversion = round(conv_raw * 100, 2) if conv_raw < 1 else round(conv_raw, 2)

            rows.append({
                "ID":            item_id,
                "Nome":          item.get("item_name", ""),
                "SKU":           item.get("item_sku", ""),
                "Status":        item.get("item_status", ""),
                "Est. Vendedor": seller_stock,
                "Est. Full":     shopee_stock,
                "Preço (R$)":    preco,
                "Vendas":        sold,
                "Views":         views,
                "Conversão (%)": conversion,
                "Curtidas":      likes,
            })

        df = pd.DataFrame(rows)

        # Filtro por nome se busca for do tipo Nome
        if tipo_busca == "Nome" and busca.strip():
            df = df[df["Nome"].str.contains(busca.strip(), case=False, na=False)]

        st.session_state["produtos_df"] = df
        st.success(f"✅ {len(df)} produto(s) carregado(s)")

    # ── Exibição da tabela ────────────────────────────────────────────────────
    if st.session_state.get("produtos_df") is not None:
        df = st.session_state["produtos_df"]

        filtro = st.text_input("🔎 Filtrar por nome na tabela", key="filtro_tabela")
        df_exibir = df[df["Nome"].str.contains(filtro, case=False, na=False)] if filtro else df

        # Métricas rápidas
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("📦 Produtos",      f"{len(df_exibir):,}")
        m2.metric("🏷 Est. Vendedor", f"{df_exibir['Est. Vendedor'].sum():,}")
        m3.metric("👁 Views",         f"{df_exibir['Views'].sum():,}")
        m4.metric("🛒 Vendas",        f"{df_exibir['Vendas'].sum():,}")
        m5.metric("❤️ Curtidas",      f"{df_exibir['Curtidas'].sum():,}")
        conv_positivos = df_exibir[df_exibir["Conversão (%)"] > 0]["Conversão (%)"]
        avg_conv = conv_positivos.mean() if not conv_positivos.empty else 0
        m6.metric("📊 Conv. Média",   f"{avg_conv:.2f}%")

        st.caption(f"Exibindo **{len(df_exibir)}** produto(s)")

        st.dataframe(
            df_exibir,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preço (R$)":    st.column_config.NumberColumn(format="R$ %.2f"),
                "Conversão (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Est. Vendedor": st.column_config.NumberColumn(),
                "Est. Full":     st.column_config.NumberColumn(),
                "Views":         st.column_config.NumberColumn(),
                "Vendas":        st.column_config.NumberColumn(),
                "Curtidas":      st.column_config.NumberColumn(),
            },
        )

        csv = df_exibir.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Exportar CSV",
            data=csv,
            file_name="produtos_shopee.csv",
            mime="text/csv",
        )
