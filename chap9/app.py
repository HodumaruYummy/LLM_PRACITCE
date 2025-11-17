import streamlit as st
from rag_gen import document_chain   # or retriever.py
from langchain_core.messages import HumanMessage

st.title("RAG City QA")

query = st.text_input("질문을 입력하세요")

if st.button("질문하기"):
    chat_history = []
    chat_history.append(HumanMessage(content=query))

    response = document_chain.invoke({
        "messages": chat_history,
        "query": query
    })

    st.write("### 📌 응답")
    st.write(response)
