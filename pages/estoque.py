import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<p class="section-title">📦 Estoque</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Consulte e atualize o estoque dos seus produtos</p>', unsafe_allow_html=True)

    st.info("Primeiro carregue os produtos para depois atualizar o estoque individualmente.")

    if st.button("🔍 Carregar Produtos para Edição de Estoque"):
        with st.spinner("Buscando produtos..."):
            result = sc.get_item_list(offset=0, page_size=50, status="NORMAL")

        if result.get("error"):
            st.error(f"❌ Erro: {result['error']}")
            return

        items = result.get("response", {}).get("item", [])
        if not items:
            st.info("Nenhum produto encontrado.")
            return

        item_ids = [i["item_id"] for i in items]
        with st.spinner("Carregando detalhes..."):
            detail_result = sc.get_item_base_info(item_ids)

        detail_items = detail_result.get("response", {}).get("item_list", [])
        st.session_state["estoque_items"] = detail_items
        st.success(f"✅ {len(detail_items)} produto(s) carregado(s)")

    if st.session_state.get("estoque_items"):
        st.divider()
        st.markdown("### Atualizar Estoque")

        items = st.session_state["estoque_items"]
        nomes = [f"{i.get('item_id')} — {i.get('item_name', '')[:60]}" for i in items]
        escolha = st.selectbox("Selecione o produto", nomes)
        idx = nomes.index(escolha)
        item = items[idx]

        item_id = item.get("item_id")
        models = item.get("models", [])

        if models:
            model_names = [m.get("model_name", f"Variação {m.get('model_id')}") for m in models]
            model_escolha = st.selectbox("Selecione a variação", model_names)
            model_idx = model_names.index(model_escolha)
            model = models[model_idx]
            model_id = model.get("model_id", 0)
            estoque_atual = model.get("stock_info_v2", {}).get("summary_info", {}).get("total_reserved_stock", 0)
        else:
            model_id = 0
            estoque_atual = item.get("stock_info_v2", {}).get("summary_info", {}).get("total_reserved_stock", 0)

        novo_estoque = st.number_input("Novo estoque", min_value=0, value=int(estoque_atual), step=1)

        if st.button("💾 Atualizar Estoque"):
            with st.spinner("Atualizando..."):
                res = sc.update_stock(item_id, model_id, novo_estoque)
            if res.get("error"):
                st.error(f"❌ Erro: {res['error']}")
            else:
                st.success("✅ Estoque atualizado com sucesso!")
                st.json(res)
