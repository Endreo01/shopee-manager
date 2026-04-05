import streamlit as st
import pandas as pd
import time
import shopee_client as sc

def render():
    st.markdown('<p class="section-title">💰 Atualização de Preços</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Individual ou em massa via CSV</p>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["✏️ Individual", "📊 Em Massa (CSV)"])

    with tab1:
        col1, col2, col3 = st.columns(3)
        item_id   = col1.number_input("Item ID *", min_value=1, value=1)
        model_id  = col2.number_input("Model ID (0 = sem variação)", min_value=0, value=0)
        new_price = col3.number_input("Novo Preço (R$) *", min_value=0.01, value=99.90, format="%.2f")
        if st.button("💰 Atualizar Preço"):
            with st.spinner("Atualizando..."):
                r = sc.update_price(item_id, model_id, new_price)
            if "error" in r or r.get("response", {}).get("failure_list"):
                st.error(f"Falhou: {r}")
            else:
                st.success(f"✅ Item {item_id} → R$ {new_price:.2f}")

    with tab2:
        template = pd.DataFrame({"item_id":[1234567,9876543],"model_id":[0,0],"new_price":[99.90,49.50]})
        st.download_button("⬇️ Baixar Template CSV", template.to_csv(index=False).encode(), "template_precos.csv", "text/csv")
        uploaded = st.file_uploader("📁 Carregar CSV", type=["csv"])
        if uploaded:
            df = pd.read_csv(uploaded)
            if not {"item_id","model_id","new_price"}.issubset(df.columns):
                st.error("Colunas obrigatórias: item_id, model_id, new_price"); return
            st.dataframe(df, use_container_width=True)
            st.info(f"📋 {len(df)} itens prontos para atualização")
            if st.button("🚀 Atualizar Todos"):
                prog = st.progress(0, text="Iniciando...")
                ok = fail = 0
                for i, row in df.iterrows():
                    r = sc.update_price(int(row["item_id"]), int(row["model_id"]), float(row["new_price"]))
                    if "error" in r or r.get("response",{}).get("failure_list"): fail += 1
                    else: ok += 1
                    prog.progress((i+1)/len(df), text=f"{i+1}/{len(df)} processados...")
                    time.sleep(0.3)  # respeita rate limit
                prog.empty()
                st.success(f"✅ {ok} atualizados | ❌ {fail} com falha")