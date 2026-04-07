import streamlit as st
import shopee_client as sc
import pandas as pd


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_stock(item: dict) -> tuple[int, int]:
    """Retorna (seller_stock, shopee_stock)."""
    stock_info = item.get("stock_info_v2", {})
    seller_list = stock_info.get("seller_stock", [])
    shopee_list = stock_info.get("shopee_stock", [])
    seller = seller_list[0].get("stock", 0) if seller_list else 0
    shopee = shopee_list[0].get("stock", 0) if shopee_list else 0
    return seller, shopee


def _get_price(item: dict) -> float:
    price_info = item.get("price_info", [{}])
    return price_info[0].get("current_price", 0) if price_info else 0


def _build_rows(detail_items: list, extra_map: dict) -> list[dict]:
    """Mescla base_info + extra_info nos campos corretos da API."""
    rows = []
    for item in detail_items:
        item_id = item.get("item_id")
        extra   = extra_map.get(item_id, {})

        seller_stock, shopee_stock = _get_stock(item)
        preco = _get_price(item)

        # Campos confirmados via debug: sale, views, likes, rating_star, comment_count
        sold        = extra.get("sale", 0) or 0
        views       = extra.get("views", 0) or 0
        likes       = extra.get("likes", 0) or 0
        rating      = extra.get("rating_star", 0) or 0
        comments    = extra.get("comment_count", 0) or 0
        conversion  = round((sold / views * 100), 2) if views > 0 else 0.0

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
            "Avaliação":     rating,
            "Comentários":   comments,
        })
    return rows


def _fetch_extra_map(item_ids: list[int]) -> dict:
    """Busca extra_info em lotes de 50 e retorna dict keyed por item_id."""
    extra_map = {}
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i:i + 50]
        res   = sc.get_item_extra_info(batch)
        # A API retorna "item_list" neste endpoint (confirmado via debug)
        for ei in res.get("response", {}).get("item_list", []):
            extra_map[ei.get("item_id")] = ei
    return extra_map


def _fetch_base_list(item_ids: list[int], progress_label: str = "Base info...") -> list[dict]:
    """Busca base_info em lotes de 50 com barra de progresso."""
    detail_items = []
    p = st.progress(0, text=progress_label)
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i:i + 50]
        res   = sc.get_item_base_info(batch)
        detail_items.extend(res.get("response", {}).get("item_list", []))
        p.progress(min((i + 50) / len(item_ids), 1.0))
    p.empty()
    return detail_items


# ── render ────────────────────────────────────────────────────────────────────

def render():
    st.markdown('<p class="section-title">🛍️ Produtos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Listagem e busca de produtos da sua loja Shopee</p>', unsafe_allow_html=True)

    # ── Filtros ───────────────────────────────────────────────────────────────
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
            "Nome":            "Digite parte do nome...",
            "SKU do Vendedor": "Ex: 15314",
            "ID da Shopee":    "Ex: 41864392939  (separe por vírgula para vários)",
        }
        busca = st.text_input("Termo de busca", placeholder=placeholder_map[tipo_busca])

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

    # ── Busca ─────────────────────────────────────────────────────────────────
    if btn_carregar:
        item_ids = []

        # ROTA 1: ID direto — vai direto para get_item_base_info
        if tipo_busca == "ID da Shopee" and busca.strip():
            raw = [x.strip() for x in busca.replace(",", " ").split() if x.strip().isdigit()]
            if not raw:
                st.error("❌ ID inválido. Digite apenas números.")
                return
            item_ids = [int(i) for i in raw]

        # ROTA 2: SKU — carrega catálogo e filtra localmente pelo item_sku
        # (search_item é endpoint público, não busca na sua loja)
        elif tipo_busca == "SKU do Vendedor" and busca.strip():
            sku_alvo = busca.strip().lower()
            st.info("⚙️ Buscando pelo SKU no catálogo da loja...")

            with st.spinner("Carregando lista de produtos..."):
                all_ids_temp = []
                offset = 0
                while True:
                    result    = sc.get_item_list(offset=offset, page_size=100, status=status)
                    items_tmp = result.get("response", {}).get("item", [])
                    if not items_tmp:
                        break
                    all_ids_temp.extend(i["item_id"] for i in items_tmp)
                    has_next = result.get("response", {}).get("has_next_page", False)
                    if not has_next or not carregar_todos:
                        break
                    offset += 100

            with st.spinner("Filtrando por SKU..."):
                matched = []
                prog = st.progress(0, text="Verificando SKUs...")
                for i in range(0, len(all_ids_temp), 50):
                    batch = all_ids_temp[i:i + 50]
                    base_res = sc.get_item_base_info(batch)
                    for it in base_res.get("response", {}).get("item_list", []):
                        if sku_alvo in (it.get("item_sku") or "").lower():
                            matched.append(it["item_id"])
                    prog.progress(min((i + 50) / max(len(all_ids_temp), 1), 1.0))
                prog.empty()

            if not matched:
                st.info(f"Nenhum produto encontrado com o SKU **{busca}**.")
                return
            item_ids = matched

        # ROTA 3: Lista normal (com filtro de nome aplicado depois)
        else:
            all_items = []
            offset    = 0

            with st.spinner("Buscando lista de produtos..."):
                prog = st.progress(0, text="Carregando página 1...")
                while True:
                    result = sc.get_item_list(offset=offset, page_size=100, status=status)
                    if result.get("error"):
                        st.error(f"❌ Erro: {result['error']}")
                        return
                    response    = result.get("response", {})
                    items       = response.get("item", [])
                    all_items.extend(items)
                    total_count = response.get("total_count", len(all_items))
                    has_next    = response.get("has_next_page", False)
                    prog.progress(
                        min(len(all_items) / max(total_count, 1), 1.0),
                        text=f"Lista: {len(all_items)} de {total_count} produtos...",
                    )
                    if not has_next or not carregar_todos:
                        break
                    offset += 100
                prog.empty()

            if not all_items:
                st.info("Nenhum produto encontrado.")
                return
            item_ids = [i["item_id"] for i in all_items]

        # ── Busca detalhes ────────────────────────────────────────────────────
        with st.spinner(f"Carregando base info de {len(item_ids)} produto(s)..."):
            detail_items = _fetch_base_list(item_ids)

        with st.spinner("Carregando dados de performance..."):
            extra_map = _fetch_extra_map(item_ids)

        # ── Monta tabela ──────────────────────────────────────────────────────
        rows = _build_rows(detail_items, extra_map)
        df   = pd.DataFrame(rows)

        if tipo_busca == "Nome" and busca.strip():
            df = df[df["Nome"].str.contains(busca.strip(), case=False, na=False)]

        if df.empty:
            st.info("Nenhum produto encontrado com os filtros aplicados.")
            return

        st.session_state["produtos_df"] = df
        st.success(f"✅ {len(df)} produto(s) carregado(s)")

    # ── Tabela ────────────────────────────────────────────────────────────────
    if st.session_state.get("produtos_df") is not None:
        df = st.session_state["produtos_df"]

        filtro    = st.text_input("🔎 Filtrar por nome na tabela", key="filtro_tabela")
        df_exibir = df[df["Nome"].str.contains(filtro, case=False, na=False)] if filtro else df

        # Métricas
        m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
        m1.metric("📦 Produtos",      f"{len(df_exibir):,}")
        m2.metric("🏷 Est. Vendedor", f"{df_exibir['Est. Vendedor'].sum():,}")
        m3.metric("👁 Views",         f"{df_exibir['Views'].sum():,}")
        m4.metric("🛒 Vendas",        f"{df_exibir['Vendas'].sum():,}")
        m5.metric("❤️ Curtidas",      f"{df_exibir['Curtidas'].sum():,}")
        conv_pos = df_exibir[df_exibir["Conversão (%)"] > 0]["Conversão (%)"]
        m6.metric("📊 Conv. Média",   f"{conv_pos.mean():.2f}%" if not conv_pos.empty else "0.00%")
        avg_rating = df_exibir[df_exibir["Avaliação"] > 0]["Avaliação"].mean()
        m7.metric("⭐ Avaliação",     f"{avg_rating:.2f}" if not pd.isna(avg_rating) else "—")

        st.caption(f"Exibindo **{len(df_exibir)}** produto(s)")

        st.dataframe(
            df_exibir,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preço (R$)":    st.column_config.NumberColumn(format="R$ %.2f"),
                "Conversão (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Avaliação":     st.column_config.NumberColumn(format="%.2f ⭐"),
                "Est. Vendedor": st.column_config.NumberColumn(),
                "Est. Full":     st.column_config.NumberColumn(),
                "Views":         st.column_config.NumberColumn(),
                "Vendas":        st.column_config.NumberColumn(),
                "Curtidas":      st.column_config.NumberColumn(),
                "Comentários":   st.column_config.NumberColumn(),
            },
        )

        csv = df_exibir.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Exportar CSV",
            data=csv,
            file_name="produtos_shopee.csv",
            mime="text/csv",
        )
