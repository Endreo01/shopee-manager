import streamlit as st
import shopee_client as sc
import pandas as pd


def _get_stock(item):
    stock_info = item.get("stock_info_v2", {})
    seller_list = stock_info.get("seller_stock", [])
    shopee_list = stock_info.get("shopee_stock", [])
    seller = seller_list[0].get("stock", 0) if seller_list else 0
    shopee = shopee_list[0].get("stock", 0) if shopee_list else 0
    return seller, shopee


def _get_price(item):
    price_info = item.get("price_info", [{}])
    return price_info[0].get("current_price", 0) if price_info else 0


def _build_rows(detail_items, extra_map):
    rows = []
    for item in detail_items:
        item_id = item.get("item_id")
        extra = extra_map.get(item_id, {})
        seller_stock, shopee_stock = _get_stock(item)
        preco = _get_price(item)
        sold = extra.get("sale", 0) or 0
        views = extra.get("views", 0) or 0
        likes = extra.get("likes", 0) or 0
        rating = extra.get("rating_star", 0) or 0
        comments = extra.get("comment_count", 0) or 0
        conversion = round((sold / views * 100), 2) if views > 0 else 0.0
        rows.append({
            "ID": item_id,
            "Nome": item.get("item_name", ""),
            "SKU": item.get("item_sku", ""),
            "Status": item.get("item_status", ""),
            "Est. Vendedor": seller_stock,
            "Est. Full": shopee_stock,
            "Preco (R$)": preco,
            "Vendas": sold,
            "Views": views,
            "Conversao (%)": conversion,
            "Curtidas": likes,
            "Avaliacao": rating,
            "Comentarios": comments,
        })
    return rows


def _fetch_extra_map(item_ids):
    extra_map = {}
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i:i + 50]
        res = sc.get_item_extra_info(batch)
        for ei in res.get("response", {}).get("item_list", []):
            extra_map[ei.get("item_id")] = ei
    return extra_map


def _fetch_base_list(item_ids, progress_label="Carregando detalhes..."):
    detail_items = []
    p = st.progress(0, text=progress_label)
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i:i + 50]
        res = sc.get_item_base_info(batch)
        detail_items.extend(res.get("response", {}).get("item_list", []))
        p.progress(min((i + 50) / len(item_ids), 1.0))
    p.empty()
    return detail_items


def _get_all_ids_da_loja(status, carregar_todos):
    all_ids = []
    offset = 0
    p = st.progress(0, text="Carregando lista da loja...")
    while True:
        result = sc.get_item_list(offset=offset, page_size=100, status=status)
        items = result.get("response", {}).get("item", [])
        if not items:
            break
        all_ids.extend(i["item_id"] for i in items)
        total = result.get("response", {}).get("total_count", len(all_ids))
        has_next = result.get("response", {}).get("has_next_page", False)
        p.progress(min(len(all_ids) / max(total, 1), 1.0),
                   text=f"Carregando: {len(all_ids)} de {total}...")
        if not has_next or not carregar_todos:
            break
        offset += 100
    p.empty()
    return all_ids


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
        )

    with col_busca:
        placeholder_map = {
            "Nome": "Digite parte do nome...",
            "SKU do Vendedor": "Digite o SKU exato (ex: 15314)",
            "ID da Shopee": "Ex: 41864392939  (separe por virgula para varios)",
        }
        busca = st.text_input("Termo de busca", placeholder=placeholder_map[tipo_busca])

    carregar_todos = st.checkbox(
        "Carregar todos os produtos (pode demorar para catalogos grandes)",
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

        # ROTA 1: ID direto
        if tipo_busca == "ID da Shopee" and busca.strip():
            raw = [x.strip() for x in busca.replace(",", " ").split() if x.strip().isdigit()]
            if not raw:
                st.error("ID invalido. Digite apenas numeros.")
                return
            item_ids = [int(i) for i in raw]

        # ROTA 2: SKU exato na propria loja
        elif tipo_busca == "SKU do Vendedor" and busca.strip():
            sku_alvo = busca.strip().lower()
            st.info("Buscando pelo SKU exato no catalogo da loja...")

            with st.spinner("Carregando lista da loja..."):
                all_ids_temp = _get_all_ids_da_loja(status, carregar_todos)

            matched = []
            prog = st.progress(0, text="Verificando SKUs...")
            for i in range(0, len(all_ids_temp), 50):
                batch = all_ids_temp[i:i + 50]
                base_res = sc.get_item_base_info(batch)
                for it in base_res.get("response", {}).get("item_list", []):
                    # Comparacao EXATA: strip + lower em ambos
                    item_sku = (it.get("item_sku") or "").strip().lower()
                    if item_sku == sku_alvo:
                        matched.append(it["item_id"])
                prog.progress(min((i + 50) / max(len(all_ids_temp), 1), 1.0))
            prog.empty()

            if not matched:
                st.info(f"Nenhum produto encontrado com o SKU exato: {busca}")
                return
            item_ids = matched

        # ROTA 3: Lista normal / filtro por nome
        else:
            with st.spinner("Buscando lista de produtos..."):
                all_ids_temp = _get_all_ids_da_loja(status, carregar_todos)
            if not all_ids_temp:
                st.info("Nenhum produto encontrado.")
                return
            item_ids = all_ids_temp

        with st.spinner(f"Carregando detalhes de {len(item_ids)} produto(s)..."):
            detail_items = _fetch_base_list(item_ids)

        with st.spinner("Carregando dados de performance..."):
            extra_map = _fetch_extra_map(item_ids)

        rows = _build_rows(detail_items, extra_map)
        df = pd.DataFrame(rows)

        if tipo_busca == "Nome" and busca.strip():
            df = df[df["Nome"].str.contains(busca.strip(), case=False, na=False)]

        if df.empty:
            st.info("Nenhum produto encontrado com os filtros aplicados.")
            return

        st.session_state["produtos_df"] = df
        st.success(f"✅ {len(df)} produto(s) carregado(s)")

    if st.session_state.get("produtos_df") is not None:
        df = st.session_state["produtos_df"]

        filtro = st.text_input("🔎 Filtrar por nome na tabela", key="filtro_tabela")
        df_exibir = df[df["Nome"].str.contains(filtro, case=False, na=False)] if filtro else df

        m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
        m1.metric("📦 Produtos", f"{len(df_exibir):,}")
        m2.metric("🏷 Est. Vendedor", f"{df_exibir['Est. Vendedor'].sum():,}")
        m3.metric("👁 Views", f"{df_exibir['Views'].sum():,}")
        m4.metric("🛒 Vendas", f"{df_exibir['Vendas'].sum():,}")
        m5.metric("❤️ Curtidas", f"{df_exibir['Curtidas'].sum():,}")
        conv_pos = df_exibir[df_exibir["Conversao (%)"] > 0]["Conversao (%)"]
        m6.metric("📊 Conv. Media", f"{conv_pos.mean():.2f}%" if not conv_pos.empty else "0.00%")
        avg_r = df_exibir[df_exibir["Avaliacao"] > 0]["Avaliacao"].mean()
        m7.metric("⭐ Avaliacao", f"{avg_r:.2f}" if avg_r == avg_r else "--")

        st.caption(f"Exibindo {len(df_exibir)} produto(s)")

        st.dataframe(
            df_exibir,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preco (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Conversao (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Avaliacao": st.column_config.NumberColumn(format="%.2f ⭐"),
                "Est. Vendedor": st.column_config.NumberColumn(),
                "Est. Full": st.column_config.NumberColumn(),
                "Views": st.column_config.NumberColumn(),
                "Vendas": st.column_config.NumberColumn(),
                "Curtidas": st.column_config.NumberColumn(),
                "Comentarios": st.column_config.NumberColumn(),
            },
        )

        csv = df_exibir.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Exportar CSV",
            data=csv,
            file_name="produtos_shopee.csv",
            mime="text/csv",
        )
