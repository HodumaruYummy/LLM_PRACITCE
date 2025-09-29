import streamlit as st
from dotenv import load_dotenv
import os
import requests

load_dotenv()

# (0) 사이드바에서 api_key 입력
with st.sidebar:
    upstage_api_key_env = os.getenv("SOLAR_API_KEY")
    upstage_api_key = st.text_input(
        "Upstage API Key (없으면 .env의 SOLAR_API_KEY 사용)",
        value=upstage_api_key_env if upstage_api_key_env else "",
        type="password",
        key="chatbot_api_key",
    )

st.title("💬 Chatbot (Upstage API 연동)")

# (1) 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "system", "content": "You are a helpful assistant."},
    ]

# (2) 이전 대화 출력
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# (3) 사용자 입력 처리
if prompt := st.chat_input():
    api_key = upstage_api_key or upstage_api_key_env
    if not api_key:
        st.info("Upstage API 키가 필요합니다.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "solar-pro2",  # 또는 solar-pro2
        "messages": st.session_state.messages,
        "temperature": 0.7,
        "max_tokens": 512,
        "stream": False,
    }

    response = requests.post(
        "https://api.upstage.ai/v1/chat/completions",
        headers=headers,
        json=payload,
    )

    if response.status_code == 200:
        msg = response.json()["choices"][0]["message"]["content"]
        st.session_state.messages.append({"role": "assistant", "content": msg})
        st.chat_message("assistant").write(msg)
    else:
        st.error(f"API 호출 실패: {response.status_code} - {response.text}")
