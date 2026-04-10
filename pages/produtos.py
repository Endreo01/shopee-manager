import streamlit as st
import shopee_client as sc
import pandas as pd


def _get_stock(item):
    info = item.get("stock_info_v2", {})
    sl = info.get("seller_stock", [])
    sh = info.get("shopee_stock", [])
    return (sl[0].get("stock", 0) if sl else 0), (sh[0].get("stock", 0) if sh else 0)


def _get_price(item):
    pi = item.get("price_info", [{}])
    return pi[0].get("current_price", 0) if pi else 0


def _build_rows(detail_items, extra_map):
    rows = []
    for item in detail_items:
        iid = item.get("item_id")
        e = extra_map.get(iid, {})
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


def _fetch_extra_map(item_ids):
    extra_map = {}
    for i in range(0, len(item_ids), 50):
        res = sc.get_item_extra_info(item_ids[i:i+50])
        for ei in res.get("response", {}).get("item_list", []):
            extra_map[ei.get("item_id")] = ei
    return extra_map


def _fetch_base_list(item_ids, label="Carregando detalhes..."):
    items = []
    p = st.progress(0, text=label)
    for i in range(0, len(item_ids), 50):
        res = sc.get_item_base_info(item_ids[i:i+50])
        items.extend(res.get("response", {}).get("item_list", []))
        p.progress(min((i+50)/len(item_ids), 1.0))
    p.empty()
    return items


def _carregar_todos_ids(status, carregar_todos=True):
    all_ids = []
    offset = 0
    p = st.progress(0, text="Carregando lista da loja...")
    while True:
        result = sc.get_item_list(offset=offset, page_size=100, status=status)
        if result.get("error"):
            st.error(f"Erro API: {result['error']}")
            break
        items = result.get("response", {}).get("item", [])
        if not items:
            break
        all_ids.extend(i["item_id"] for i in items)
        total = result.get("response", {}).get("total_count", len(all_ids))
        has_next = result.get("response", {}).get("has_next_page", False)
        p.progress(
            min(len(all_ids) / max(total, 1), 1.0),
            text=f"Lista: {len(all_ids)} de {total}...",
        )
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
        status = st.selectbox("Status", ["NORMAL", "BANNED", "DELETED", "UNLIST"])
    with col_tipo:
        tipo_busca = st.selectbox("Buscar por", ["Nome", "SKU do Vendedor", "ID da Shopee"])
    with col_busca:
        ph = {
            "Nome":            "Digite parte do nome...",
            "SKU do Vendedor": "SKU exato (ex: 15314)",
            "ID da Shopee":    "Ex: 41864392939  (virgula para varios)",
        }
        busca = st.text_input("Termo de busca", placeholder=ph[tipo_busca])

    carregar_todos = st.checkbox("Carregar todos os produtos (pode demorar)", value=False)

    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        btn_buscar = st.button("Carregar / Buscar", type="primary", use_container_width=True)
    with c2:
        btn_limpar = st.button("Limpar", use_container_width=True)

    if btn_limpar:
        st.session_state.pop("produtos_df", None)
        st.rerun()

    if btn_buscar:
        # Limpa resultado anterior para não exibir dado velho durante nova busca
        st.session_state.pop("produtos_df", None)
        st.session_state.pop("produtos_aviso", None)
        item_ids = []

        # ROTA 1: ID direto
        if tipo_busca == "ID da Shopee" and busca.strip():
            raw = [x.strip() for x in busca.replace(",", " ").split() if x.strip().isdigit()]
            if not raw:
                st.error("ID invalido. Digite apenas numeros.")
                st.stop()
            item_ids = [int(x) for x in raw]

        # ROTA 2: SKU exato — percorre TODOS os IDs da loja (ignora checkbox)
        elif tipo_busca == "SKU do Vendedor" and busca.strip():
            sku_alvo = busca.strip().lower()
            st.info(f"Buscando SKU exato '{busca}' em todos os produtos da loja...")

            with st.spinner("Carregando lista completa..."):
                all_ids_temp = _carregar_todos_ids(status, carregar_todos=True)

            if not all_ids_temp:
                st.session_state["produtos_aviso"] = "Nenhum produto encontrado na loja."
                st.stop()

            matched = []
            prog = st.progress(0, text="Verificando SKUs...")
            for i in range(0, len(all_ids_temp), 50):
                batch = all_ids_temp[i:i+50]
                res = sc.get_item_base_info(batch)
                for it in res.get("response", {}).get("item_list", []):
                    sku_item = (it.get("item_sku") or "").strip().lower()
                    if sku_item == sku_alvo:
                        matched.append(it["item_id"])
                prog.progress(min((i+50) / max(len(all_ids_temp), 1), 1.0),
                              text=f"Verificando {min(i+50, len(all_ids_temp))} de {len(all_ids_temp)}...")
            prog.empty()

            if not matched:
                st.session_state["produtos_aviso"] = f"SKU '{busca}' não encontrado. Verifique se está exatamente igual ao cadastrado na Shopee."
                st.stop()
            item_ids = matched

        # ROTA 3: Lista / Nome
        else:
            with st.spinner("Carregando lista de produtos..."):
                all_ids_temp = _carregar_todos_ids(status, carregar_todos)
            if not all_ids_temp:
                st.session_state["produtos_aviso"] = "Nenhum produto encontrado."
                st.stop()
            item_ids = all_ids_temp

        with st.spinner(f"Buscando detalhes de {len(item_ids)} produto(s)..."):
            detail_items = _fetch_base_list(item_ids)

        with st.spinner("Buscando performance (views, vendas, curtidas)..."):
            extra_map = _fetch_extra_map(item_ids)

        rows = _build_rows(detail_items, extra_map)
        df = pd.DataFrame(rows)

        if tipo_busca == "Nome" and busca.strip():
            df = df[df["Nome"].str.contains(busca.strip(), case=False, na=False)]

        if df.empty:
            st.session_state["produtos_aviso"] = "Nenhum produto encontrado."
            st.stop()

        st.session_state["produtos_df"] = df
        st.success(f"✅ {len(df)} produto(s) carregado(s)")

    # Exibe aviso persistente se a última busca não retornou resultado
    if st.session_state.get("produtos_aviso"):
        st.warning(st.session_state["produtos_aviso"])

    if st.session_state.get("produtos_df") is not None:
        df = st.session_state["produtos_df"]

        filtro = st.text_input("Filtrar por nome na tabela", key="filtro_tabela")
        dfe = df[df["Nome"].str.contains(filtro, case=False, na=False)] if filtro else df

        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        c1.metric("Produtos",      f"{len(dfe):,}")
        c2.metric("Est. Vendedor", f"{dfe['Est. Vendedor'].sum():,}")
        c3.metric("Views",         f"{dfe['Views'].sum():,}")
        c4.metric("Vendas",        f"{dfe['Vendas'].sum():,}")
        c5.metric("Curtidas",      f"{dfe['Curtidas'].sum():,}")
        cp = dfe[dfe["Conversao (%)"] > 0]["Conversao (%)"]
        c6.metric("Conv. Media",   f"{cp.mean():.2f}%" if not cp.empty else "0.00%")
        ar = dfe[dfe["Avaliacao"] > 0]["Avaliacao"].mean()
        c7.metric("Avaliacao",     f"{ar:.2f}" if ar == ar else "--")

        st.caption(f"Exibindo {len(dfe)} produto(s)")

        st.dataframe(
            dfe,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preco (R$)":    st.column_config.NumberColumn(format="R$ %.2f"),
                "Conversao (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Avaliacao":     st.column_config.NumberColumn(format="%.2f"),
                "Est. Vendedor": st.column_config.NumberColumn(),
                "Est. Full":     st.column_config.NumberColumn(),
                "Views":         st.column_config.NumberColumn(),
                "Vendas":        st.column_config.NumberColumn(),
                "Curtidas":      st.column_config.NumberColumn(),
                "Comentarios":   st.column_config.NumberColumn(),
            },
        )

        csv = dfe.to_csv(index=False).encode("utf-8")
        st.download_button("Exportar CSV", data=csv,
                           file_name="produtos_shopee.csv", mime="text/csv")