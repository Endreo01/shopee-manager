import streamlit as st
import shopee_client as sc
import pandas as pd


def render():
    st.markdown('<p class="section-title">🛍️ Produtos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Listagem e busca de produtos da sua loja Shopee</p>', unsafe_allow_html=True)

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
            "SKU do Vendedor": "Ex: 15314",
            "ID da Shopee":    "Ex: 41864392939  (separe por vírgula para vários)",
        }
        busca = st.text_input("Termo de busca", placeholder=placeholder_map[tipo_busca])

    # Debug temporário — ajuda a descobrir os campos reais do extra_info
    debug_mode = st.checkbox("🔧 Modo debug (mostra campos brutos da API)", value=False)

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

    if btn_carregar:
        item_ids = []

        # ── ROTA 1: ID direto ─────────────────────────────────────────────────
        if tipo_busca == "ID da Shopee" and busca.strip():
            raw_ids = [x.strip() for x in busca.replace(",", " ").split() if x.strip().isdigit()]
            if not raw_ids:
                st.error("❌ ID inválido. Digite apenas números.")
                return
            item_ids = [int(i) for i in raw_ids]

        # ── ROTA 2: SKU ───────────────────────────────────────────────────────
        elif tipo_busca == "SKU do Vendedor" and busca.strip():
            sku_alvo = busca.strip().lower()

            with st.spinner("Buscando pelo SKU via API..."):
                res = sc.search_item(sku_alvo, search_by="sku")
                id_list = res.get("response", {}).get("item_id_list", [])

            if id_list:
                # FIX: item_id_list pode ser lista de ints OU lista de dicts
                if id_list and isinstance(id_list[0], dict):
                    item_ids = [i["item_id"] for i in id_list]
                else:
                    item_ids = [int(i) for i in id_list]
            else:
                # Fallback: filtra localmente pelo SKU
                st.info("⚙️ Buscando em todo o catálogo pelo SKU (fallback)...")
                with st.spinner("Carregando catálogo..."):
                    all_ids_temp = []
                    offset = 0
                    while True:
                        result = sc.get_item_list(offset=offset, page_size=100, status=status)
                        items_temp = result.get("response", {}).get("item", [])
                        if not items_temp:
                            break
                        all_ids_temp.extend(i["item_id"] for i in items_temp)
                        if not result.get("response", {}).get("has_next_page", False) or not carregar_todos:
                            break
                        offset += 100

                    matched_ids = []
                    for i in range(0, len(all_ids_temp), 50):
                        batch = all_ids_temp[i:i + 50]
                        base_res = sc.get_item_base_info(batch)
                        for it in base_res.get("response", {}).get("item_list", []):
                            if sku_alvo in (it.get("item_sku") or "").lower():
                                matched_ids.append(it["item_id"])

                if not matched_ids:
                    st.info(f"Nenhum produto encontrado com o SKU **{busca}**.")
                    return
                item_ids = matched_ids

        # ── ROTA 3: Lista normal ──────────────────────────────────────────────
        else:
            all_items = []
            offset = 0

            with st.spinner("Buscando lista de produtos..."):
                progress = st.progress(0, text="Carregando página 1...")
                while True:
                    result = sc.get_item_list(offset=offset, page_size=100, status=status)
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
                    offset += 100
                progress.empty()

            if not all_items:
                st.info("Nenhum produto encontrado.")
                return
            item_ids = [i["item_id"] for i in all_items]

        # ── Base info ─────────────────────────────────────────────────────────
        detail_items = []
        with st.spinner(f"Carregando informações de {len(item_ids)} produto(s)..."):
            p2 = st.progress(0, text="Base info...")
            for i in range(0, len(item_ids), 50):
                batch = item_ids[i:i + 50]
                res = sc.get_item_base_info(batch)
                detail_items.extend(res.get("response", {}).get("item_list", []))
                p2.progress(min((i + 50) / len(item_ids), 1.0))
            p2.empty()

        # ── Extra info ────────────────────────────────────────────────────────
        extra_map = {}
        with st.spinner("Carregando dados de performance..."):
            p3 = st.progress(0, text="Performance...")
            for i in range(0, len(item_ids), 50):
                batch = item_ids[i:i + 50]
                res = sc.get_item_extra_info(batch)
                response_extra = res.get("response", {})

                # Tenta os dois nomes de chave possíveis
                extra_items = (
                    response_extra.get("item_extra_info_list")
                    or response_extra.get("item_list")
                    or []
                )

                # DEBUG: mostra a resposta bruta da API para identificar campos corretos
                if debug_mode and i == 0:
                    st.write("**🔧 Resposta bruta do extra_info (primeiro lote):**")
                    st.json(response_extra)

                for ei in extra_items:
                    extra_map[ei.get("item_id")] = ei
                p3.progress(min((i + 50) / len(item_ids), 1.0))
            p3.empty()

        # DEBUG: mostra campos do primeiro item do extra_map
        if debug_mode and extra_map:
            primeiro = next(iter(extra_map.values()))
            st.write("**🔧 Campos disponíveis no extra_info do 1º produto:**")
            st.json(primeiro)

        # ── Monta DataFrame ───────────────────────────────────────────────────
        rows = []
        for item in detail_items:
            item_id = item.get("item_id")
            extra = extra_map.get(item_id, {})

            stock_info = item.get("stock_info_v2", {})
            seller_stock_list = stock_info.get("seller_stock", [])
            seller_stock = seller_stock_list[0].get("stock", 0) if seller_stock_list else 0
            shopee_stock_list = stock_info.get("shopee_stock", [])
            shopee_stock = shopee_stock_list[0].get("stock", 0) if shopee_stock_list else 0

            price_info = item.get("price_info", [{}])
            preco = price_info[0].get("current_price", 0) if price_info else 0

            # Fallback nos dois nomes de campo possíveis
            views = extra.get("view_count") or extra.get("page_view") or 0
            sold  = extra.get("sold_count") or extra.get("sold")      or 0
            likes = extra.get("liked_count") or extra.get("like_count") or 0

            conv_raw = extra.get("conversion_rate", 0) or 0
            if conv_raw > 0:
                conversion = round(conv_raw * 100, 2) if conv_raw < 1 else round(conv_raw, 2)
            else:
                conversion = round((sold / views * 100), 2) if views and views > 0 else 0.0

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

        if tipo_busca == "Nome" and busca.strip():
            df = df[df["Nome"].str.contains(busca.strip(), case=False, na=False)]

        st.session_state["produtos_df"] = df
        st.success(f"✅ {len(df)} produto(s) carregado(s)")

    # ── Exibição da tabela ────────────────────────────────────────────────────
    if st.session_state.get("produtos_df") is not None:
        df = st.session_state["produtos_df"]

        filtro = st.text_input("🔎 Filtrar por nome na tabela", key="filtro_tabela")
        df_exibir = df[df["Nome"].str.contains(filtro, case=False, na=False)] if filtro else df

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
