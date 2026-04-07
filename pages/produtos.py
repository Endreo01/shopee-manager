import streamlit as st
import shopee_client as sc
import pandas as pd


def render():
    st.markdown('<p class="section-title">🛍️ Produtos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Listagem de produtos ativos na sua loja Shopee</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])
    with col1:
        status = st.selectbox("Status", ["NORMAL", "BANNED", "DELETED", "UNLIST"], index=0)
    with col2:
        busca = st.text_input("Buscar por nome", placeholder="Digite parte do nome...")

    carregar_todos = st.checkbox("Carregar todos os produtos (pode demorar para catálogos grandes)", value=False)

    if st.button("🔍 Carregar Produtos"):
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
                    text=f"Lista: {len(all_items)} de {total_count} produtos..."
                )

                if not has_next or not carregar_todos:
                    break
                offset += page_size

            progress.empty()

        if not all_items:
            st.info("Nenhum produto encontrado.")
            return

        item_ids = [i["item_id"] for i in all_items]

        # --- Busca base info em lotes de 50 ---
        detail_items = []
        with st.spinner(f"Carregando informações de {len(item_ids)} produto(s)..."):
            p2 = st.progress(0, text="Base info...")
            for i in range(0, len(item_ids), 50):
                batch = item_ids[i:i+50]
                res = sc.get_item_base_info(batch)
                detail_items.extend(res.get("response", {}).get("item_list", []))
                p2.progress(min((i + 50) / len(item_ids), 1.0))
            p2.empty()

        # --- Busca extra info (views, conversão) em lotes de 50 ---
        extra_map = {}
        with st.spinner("Carregando dados de performance..."):
            p3 = st.progress(0, text="Performance...")
            for i in range(0, len(item_ids), 50):
                batch = item_ids[i:i+50]
                res = sc.get_item_extra_info(batch)
                for ei in res.get("response", {}).get("item_list", []):
                    extra_map[ei.get("item_id")] = ei
                p3.progress(min((i + 50) / len(item_ids), 1.0))
            p3.empty()

        # --- Monta tabela ---
        rows = []
        for item in detail_items:
            item_id = item.get("item_id")
            extra = extra_map.get(item_id, {})

            # Estoques
            stock_info = item.get("stock_info_v2", {})
            seller_stock_list = stock_info.get("seller_stock", [])
            seller_stock = seller_stock_list[0].get("stock", 0) if seller_stock_list else 0

            shopee_stock_list = stock_info.get("shopee_stock", [])
            shopee_stock = shopee_stock_list[0].get("stock", 0) if shopee_stock_list else 0

            # Preço
            price_info = item.get("price_info", [{}])
            preco = price_info[0].get("current_price", 0) if price_info else 0

            # Performance
            page_view = extra.get("page_view", 0) or 0
            sold = extra.get("sold", item.get("sold", 0)) or 0
            conversion = round((sold / page_view * 100), 2) if page_view and page_view > 0 else 0.0
            like_count = extra.get("like_count", 0) or 0

            rows.append({
                "ID": item_id,
                "Nome": item.get("item_name", ""),
                "Status": item.get("item_status", ""),
                "Est. Vendedor": seller_stock,
                "Est. Full": shopee_stock,
                "Preço (R$)": preco,
                "Vendas": sold,
                "Views": page_view,
                "Conversão (%)": conversion,
                "Curtidas": like_count,
            })

        df = pd.DataFrame(rows)

        if busca:
            df = df[df["Nome"].str.contains(busca, case=False, na=False)]

        st.session_state["produtos_df"] = df
        st.success(f"✅ {len(df)} produto(s) carregado(s)")

    if st.session_state.get("produtos_df") is not None:
        df = st.session_state["produtos_df"]

        filtro = st.text_input("🔎 Filtrar por nome na tabela", key="filtro_tabela")
        df_exibir = df[df["Nome"].str.contains(filtro, case=False, na=False)] if filtro else df

        st.caption(f"Exibindo {len(df_exibir)} produto(s)")
        st.dataframe(
            df_exibir,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preço (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Conversão (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Est. Vendedor": st.column_config.NumberColumn(),
                "Est. Full": st.column_config.NumberColumn(),
                "Views": st.column_config.NumberColumn(),
                "Vendas": st.column_config.NumberColumn(),
                "Curtidas": st.column_config.NumberColumn(),
            }
        )

        # Botão exportar CSV
        csv = df_exibir.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Exportar CSV",
            data=csv,
            file_name="produtos_shopee.csv",
            mime="text/csv"
        )
