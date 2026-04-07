import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<p class="section-title">🛍️ Produtos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Listagem de produtos ativos na sua loja Shopee</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        status = st.selectbox("Status", ["NORMAL", "BANNED", "DELETED", "UNLIST"], index=0)
    with col2:
        page_size = st.selectbox("Itens por página", [20, 50, 100], index=1)

    if st.button("🔍 Carregar Produtos", use_container_width=False):
        with st.spinner("Buscando produtos..."):
            result = sc.get_item_list(offset=0, page_size=page_size, status=status)

        if result.get("error"):
            st.error(f"❌ Erro: {result['error']}")
            return

        items = result.get("response", {}).get("item", [])
        if not items:
            st.info("Nenhum produto encontrado para o status selecionado.")
            return

        st.success(f"✅ {len(items)} produto(s) encontrado(s)")

        # Busca detalhes dos produtos
        item_ids = [i["item_id"] for i in items]
        with st.spinner("Carregando detalhes..."):
            detail_result = sc.get_item_base_info(item_ids)

        detail_items = detail_result.get("response", {}).get("item_list", [])

        rows = []
        for item in detail_items:
            rows.append({
                "ID": item.get("item_id"),
                "Nome": item.get("item_name", ""),
                "Status": item.get("item_status", ""),
                "Estoque": item.get("stock_info_v2", {}).get("summary_info", {}).get("total_reserved_stock", 0),
                "Preço (R$)": item.get("price_info", [{}])[0].get("current_price", 0) if item.get("price_info") else 0,
                "Vendas": item.get("sold", 0),
            })

        if rows:
            import pandas as pd
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.json(result)
