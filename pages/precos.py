import streamlit as st
import shopee_client as sc


def render():
    st.markdown('<p class="section-title">💰 Preços</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Consulte e atualize os preços dos seus produtos</p>', unsafe_allow_html=True)

    if st.button("🔍 Carregar Produtos para Edição de Preço"):
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
        st.session_state["precos_items"] = detail_items
        st.success(f"✅ {len(detail_items)} produto(s) carregado(s)")

    if st.session_state.get("precos_items"):
        st.divider()
        st.markdown("### Atualizar Preço")

        items = st.session_state["precos_items"]
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
            preco_atual = model.get("price_info", [{}])[0].get("current_price", 0) if model.get("price_info") else 0
        else:
            model_id = 0
            preco_atual = item.get("price_info", [{}])[0].get("current_price", 0) if item.get("price_info") else 0

        novo_preco = st.number_input("Novo preço (R$)", min_value=0.01, value=float(preco_atual or 1.0), step=0.01, format="%.2f")

        if st.button("💾 Atualizar Preço"):
            with st.spinner("Atualizando..."):
                res = sc.update_price(item_id, model_id, novo_preco)
            if res.get("error"):
                st.error(f"❌ Erro: {res['error']}")
            else:
                st.success("✅ Preço atualizado com sucesso!")
                st.json(res)
