import streamlit as st
import shopee_client as sc
import pandas as pd


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_stock(item):
    info = item.get("stock_info_v2", {})
    sl = info.get("seller_stock", [])
    sh = info.get("shopee_stock", [])
    return (sl[0].get("stock", 0) if sl else 0), (sh[0].get("stock", 0) if sh else 0)


def _get_price(item):
    pi = item.get("price_info", [{}])
    return pi[0].get("current_price", 0) if pi else 0


def _build_rows(detail_items, extra_map=None):
    if extra_map is None:
        extra_map = {}
    rows = []
    for item in detail_items:
        iid  = item.get("item_id")
        e    = extra_map.get(iid, {})
        ss, sh = _get_stock(item)
        sold  = e.get("sale", 0) or 0
        views = e.get("views", 0) or 0
        rows.append({
            "ID":            iid,
            "Nome":          item.get("item_name", ""),
            "SKU":           item.get("item_sku", ""),
            "Status":        item.get("item_status", ""),
            "Est. Vendedor": ss,
            "Est. Full":     sh,
            "Preco (R$)":    _get_price(item),
            "Vendas":        sold,
            "Views":         views,
            "Conversao (%)": round(sold / views * 100, 2) if views > 0 else 0.0,
            "Curtidas":      e.get("likes", 0) or 0,
            "Avaliacao":     e.get("rating_star", 0) or 0,
            "Comentarios":   e.get("comment_count", 0) or 0,
        })
    return rows


def _carregar_catalogo(status):
    """
    Carrega TODOS os produtos da loja com base_info + extra_info.
    Salva na session_state['catalogo_df'] e session_state['catalogo_status'].
    """
    # Passo 1 — buscar todos os IDs
    all_ids = []
    offset  = 0
    p = st.progress(0, text="Carregando lista da loja...")
    while True:
        result = sc.get_item_list(offset=offset, page_size=100, status=status)
        if result.get("error"):
            st.error(f"Erro API: {result['error']}")
            p.empty()
            return None
        items    = result.get("response", {}).get("item", [])
        if not items:
            break
        all_ids.extend(i["item_id"] for i in items)
        total    = result.get("response", {}).get("total_count", len(all_ids))
        has_next = result.get("response", {}).get("has_next_page", False)
        p.progress(
            min(len(all_ids) / max(total, 1), 1.0),
            text=f"Lista: {len(all_ids)} de {total} produtos...",
        )
        if not has_next:
            break
        offset += 100
    p.empty()

    if not all_ids:
        st.warning("Nenhum produto encontrado.")
        return None

    # Passo 2 — base_info em lotes de 50
    detail_items = []
    p2 = st.progress(0, text="Carregando detalhes dos produtos...")
    for i in range(0, len(all_ids), 50):
        res = sc.get_item_base_info(all_ids[i:i+50])
        detail_items.extend(res.get("response", {}).get("item_list", []))
        p2.progress(min((i+50) / len(all_ids), 1.0),
                    text=f"Detalhes: {min(i+50, len(all_ids))} de {len(all_ids)}...")
    p2.empty()

    # Passo 3 — extra_info (vendas, views, curtidas) em lotes de 50
    extra_map = {}
    p3 = st.progress(0, text="Carregando performance (vendas, views)...")
    for i in range(0, len(all_ids), 50):
        res = sc.get_item_extra_info(all_ids[i:i+50])
        for ei in res.get("response", {}).get("item_list", []):
            extra_map[ei.get("item_id")] = ei
        p3.progress(min((i+50) / len(all_ids), 1.0))
    p3.empty()

    rows = _build_rows(detail_items, extra_map)
    df   = pd.DataFrame(rows)
    st.session_state["catalogo_df"]     = df
    st.session_state["catalogo_status"] = status
    return df


def _atualizar_selecionados(item_ids):
    """
    Busca dados frescos (base_info + extra_info) para uma lista de IDs
    e atualiza as linhas correspondentes no catalogo_df.
    """
    detail_items = []
    for i in range(0, len(item_ids), 50):
        res = sc.get_item_base_info(item_ids[i:i+50])
        detail_items.extend(res.get("response", {}).get("item_list", []))

    extra_map = {}
    for i in range(0, len(item_ids), 50):
        res = sc.get_item_extra_info(item_ids[i:i+50])
        for ei in res.get("response", {}).get("item_list", []):
            extra_map[ei.get("item_id")] = ei

    rows    = _build_rows(detail_items, extra_map)
    df_novo = pd.DataFrame(rows)

    # Atualiza o catálogo principal linha a linha
    catalogo = st.session_state["catalogo_df"]
    catalogo = catalogo[~catalogo["ID"].isin(item_ids)]
    catalogo = pd.concat([catalogo, df_novo], ignore_index=True)
    st.session_state["catalogo_df"] = catalogo
    return df_novo


# ── Render ────────────────────────────────────────────────────────────────────

def render():
    st.markdown('<p class="section-title">🛍️ Produtos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Catálogo completo da sua loja Shopee</p>', unsafe_allow_html=True)

    # ── Barra de controles ────────────────────────────────────────────────────
    col_status, col_btn, col_clear = st.columns([1, 1.5, 1])
    with col_status:
        status = st.selectbox("Status", ["NORMAL", "BANNED", "DELETED", "UNLIST"])
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_carregar = st.button("🔄 Carregar / Atualizar Catálogo", type="primary", use_container_width=True)
    with col_clear:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_limpar = st.button("🗑️ Limpar", use_container_width=True)

    if btn_limpar:
        st.session_state.pop("catalogo_df", None)
        st.session_state.pop("catalogo_status", None)
        st.rerun()

    # ── Carrega catálogo ──────────────────────────────────────────────────────
    if btn_carregar:
        with st.spinner("Carregando catálogo completo..."):
            df = _carregar_catalogo(status)
        if df is None:
            st.stop()
        st.success(f"✅ {len(df):,} produto(s) carregado(s) no catálogo!")

    # Sem catálogo carregado — para aqui
    if st.session_state.get("catalogo_df") is None:
        st.info("👆 Clique em **Carregar / Atualizar Catálogo** para começar.")
        st.stop()

    catalogo = st.session_state["catalogo_df"]

    # ── Filtros locais (instantâneos, sem chamada à API) ──────────────────────
    st.divider()
    st.markdown("### 🔍 Filtrar no catálogo")

    col_tipo, col_busca = st.columns([1.2, 3])
    with col_tipo:
        tipo_filtro = st.selectbox("Filtrar por", ["Nome", "SKU", "ID da Shopee"])
    with col_busca:
        termo = st.text_input(
            "Termo",
            placeholder={
                "Nome":         "Digite parte do nome...",
                "SKU":          "SKU exato ou parcial (ex: 158)",
                "ID da Shopee": "Ex: 27590274924  (vírgula para vários)",
            }[tipo_filtro],
        )

    # Aplica filtro
    df_filtrado = catalogo.copy()
    if termo.strip():
        t = termo.strip()
        if tipo_filtro == "Nome":
            df_filtrado = df_filtrado[df_filtrado["Nome"].str.contains(t, case=False, na=False)]
        elif tipo_filtro == "SKU":
            df_filtrado = df_filtrado[df_filtrado["SKU"].str.contains(t, case=False, na=False)]
        elif tipo_filtro == "ID da Shopee":
            ids_busca = [int(x) for x in t.replace(",", " ").split() if x.strip().isdigit()]
            df_filtrado = df_filtrado[df_filtrado["ID"].isin(ids_busca)]

    # ── Botão atualizar dados dos filtrados ───────────────────────────────────
    col_info, col_atualizar = st.columns([3, 1])
    with col_info:
        st.caption(f"Exibindo **{len(df_filtrado):,}** de {len(catalogo):,} produto(s) no catálogo")
    with col_atualizar:
        btn_atualizar = st.button(
            "⚡ Atualizar dados",
            use_container_width=True,
            help="Busca estoque, vendas e preço atualizados para os produtos filtrados",
            disabled=df_filtrado.empty,
        )

    if btn_atualizar:
        ids_para_atualizar = df_filtrado["ID"].tolist()
        if len(ids_para_atualizar) > 200:
            st.warning(f"⚠️ Muitos produtos selecionados ({len(ids_para_atualizar)}). Refine o filtro para até 200.")
            st.stop()
        with st.spinner(f"Atualizando dados de {len(ids_para_atualizar)} produto(s)..."):
            df_filtrado = _atualizar_selecionados(ids_para_atualizar)
        st.success(f"✅ Dados atualizados para {len(df_filtrado)} produto(s)!")

    # ── Métricas ──────────────────────────────────────────────────────────────
    if not df_filtrado.empty:
        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        c1.metric("Produtos",      f"{len(df_filtrado):,}")
        c2.metric("Est. Vendedor", f"{df_filtrado['Est. Vendedor'].sum():,}")
        c3.metric("Views",         f"{df_filtrado['Views'].sum():,}")
        c4.metric("Vendas",        f"{df_filtrado['Vendas'].sum():,}")
        c5.metric("Curtidas",      f"{df_filtrado['Curtidas'].sum():,}")
        cp = df_filtrado[df_filtrado["Conversao (%)"] > 0]["Conversao (%)"]
        c6.metric("Conv. Média",   f"{cp.mean():.2f}%" if not cp.empty else "0.00%")
        ar = df_filtrado[df_filtrado["Avaliacao"] > 0]["Avaliacao"].mean()
        c7.metric("Avaliação",     f"{ar:.2f}" if pd.notna(ar) else "--")

    # ── Tabela ────────────────────────────────────────────────────────────────
    if df_filtrado.empty:
        st.info("Nenhum produto encontrado com esse filtro.")
    else:
        st.dataframe(
            df_filtrado,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preco (R$)":    st.column_config.NumberColumn(format="R$ %.2f"),
                "Conversao (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Avaliacao":     st.column_config.NumberColumn(format="%.2f ⭐"),
                "Est. Vendedor": st.column_config.NumberColumn(),
                "Est. Full":     st.column_config.NumberColumn(),
                "Views":         st.column_config.NumberColumn(),
                "Vendas":        st.column_config.NumberColumn(),
                "Curtidas":      st.column_config.NumberColumn(),
                "Comentarios":   st.column_config.NumberColumn(),
            },
        )

        csv = df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Exportar CSV",
            data=csv,
            file_name="produtos_shopee.csv",
            mime="text/csv",
        )