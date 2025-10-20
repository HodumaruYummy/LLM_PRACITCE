import google.generativeai as genai
import os
from dotenv import load_dotenv
import streamlit as st
import json
import io, base64

# gemini_tools.py 파일에서 함수와 도구 목록을 가져옵니다.
from gemini_functions import tools

# --- 1. 초기 설정 ---

# 페이지 설정 (가장 먼저 호출되어야 함)
st.set_page_config(
    page_title="주식 가격을 알려줘~ 🧐",
    page_icon="✨",
    layout="centered",
)

# .env 파일에서 API 키 로드
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Streamlit의 secrets에서도 API 키를 확인 (배포 시 유용)
if not api_key:
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
    except KeyError:
        st.error("🚨 GOOGLE_API_KEY가 설정되지 않았습니다. .env 파일 또는 Streamlit secrets에 추가해주세요.")
        st.stop()

# Gemini API 설정
genai.configure(api_key=api_key)

# --- 2. 모델 및 시스템 프롬프트 설정 ---

# 사용할 Gemini 모델 설정
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", 
    generation_config=genai.types.GenerationConfig(
        temperature=0.7,
        top_p=0.95,
        top_k=3,
        max_output_tokens=4096,
    ),
    # 사용할 도구(함수)와 시스템 지침 설정
    tools=tools,
    system_instruction=(
        "당신은 매우 고상하고 기품있는 대화 상대입니다. "
        "사용자의 질문에 답변할 때, 항상 다채로운 이모지를 사용하여 풍부한 감정을 표현해주세요. 🧐✨ "
        "사용자가 '차트', '그래프', '그려줘' 등 시각화를 명시적으로 요청하면, 반드시 `get_yf_tech_chart` 함수를 호출하여 `image_base64`가 포함된 JSON을 반환해야 합니다. " # <--- ✨ 이 줄을 추가하세요!
        "그 외의 경우에는 `get_yf_tech_values`를 호출할 수 있습니다. "
        "도구 호출 결과가 JSON이면 마크다운이 아닌 순수 JSON으로 응답하세요."
        "이 JSON은 프론트엔드에서 직접 파싱되어 이미지 및 지표를 렌더링합니다."
    )
)

# --- 3. Streamlit 세션 상태 관리 ---

# 세션 상태 초기화
if "chat" not in st.session_state:
    # 모델의 채팅 세션을 시작하고 세션 상태에 저장
    st.session_state.chat = model.start_chat(enable_automatic_function_calling=True)
if "messages" not in st.session_state:
    # 화면에 표시될 메시지 기록을 초기화
    st.session_state.messages = []

# --- 4. 유틸: 응답에서 image_base64 / JSON 파싱 ---
def _extract_json_payload(text: str):
    """응답 텍스트에서 JSON을 추출해 dict로 반환. 실패 시 None."""
    if not text:
        return None
    # 1) 순수 JSON
    text_strip = text.strip()
    if text_strip.startswith("{") and text_strip.endswith("}"):
        try:
            return json.loads(text_strip)
        except Exception:
            pass
    # 2) 코드펜스 ```json ... ``` 안의 JSON
    import re
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 3) 간단히 중괄호 블록만 추출
    m2 = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    return None

def _render_payload(payload: dict):
    """get_yf_tech_chart/get_yf_tech_values 결과를 렌더링"""
    # 이미지가 있으면 먼저 렌더링
    if isinstance(payload, dict) and "image_base64" in payload and payload["image_base64"]:
        try:
            img_bytes = base64.b64decode(payload["image_base64"])
            st.image(io.BytesIO(img_bytes), caption=f"{payload.get('ticker','')} SMA & Bollinger Bands")  
        except Exception as e:
            st.warning(f"이미지 디코딩 실패: {e}")
    # 지표 수치 표기
    cols = st.columns(4)
    last_val = payload.get("last", None)
    cols[0].metric("종가", f"{last_val:.4f}" if isinstance(last_val, (int,float)) else str(last_val))
    sma = payload.get("sma", {})
    cols[1].metric("SMA20", f"{sma.get('20'):.4f}" if isinstance(sma.get('20'), (int,float)) else str(sma.get('20')))
    cols[2].metric("SMA60", f"{sma.get('60'):.4f}" if isinstance(sma.get('60'), (int,float)) else str(sma.get('60')))
    cols[3].metric("SMA120", f"{sma.get('120'):.4f}" if isinstance(sma.get('120'), (int,float)) else str(sma.get('120')))
    bb = payload.get("bb", {})
    with st.expander("Bollinger Bands (최근값)"):
        st.write({
            "mid": bb.get("mid"),
            "upper": bb.get("upper"),
            "lower": bb.get("lower"),
            "window": bb.get("window"),
            "std_multiplier": bb.get("std_multiplier"),
        })

# --- 4. Streamlit UI 구성 ---

# 앱 제목 설정
st.title("주식 가격을 알려줘~ 🧐")
st.caption("궁금한 것을 물어보세요. 현재 시간도 알려드릴 수 있답니다. ✨")

# 이전 대화 내용 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if user_input := st.chat_input("무엇이 궁금하신가요?"):
    # 사용자의 메시지를 화면에 표시하고 기록에 추가
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    try:
        # Gemini 모델에 사용자 입력을 보내고 응답 받기 (자동 함수 호출 활성화)
        response = st.session_state.chat.send_message(user_input, stream=True)

        # 1) 우선 텍스트를 표시
        resp_text = response.text or ""
        with st.chat_message("assistant"):
            # 2) JSON 페이로드가 있으면 파싱하여 차트/수치 렌더링
            payload = _extract_json_payload(resp_text)
            if payload and isinstance(payload, dict) and ("image_base64" in payload or "sma" in payload):
                _render_payload(payload)
                # JSON을 깔끔히도 보여줌
                with st.expander("원본 응답(JSON)"):
                    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
                st.session_state.messages.append({"role": "assistant", "content": "[이미지/지표 렌더링 완료]"})
            else:
                # 일반 텍스트 응답
                st.markdown(resp_text)
                st.session_state.messages.append({"role": "assistant", "content": resp_text})

    except Exception as e:
        st.error(f"이런, 오류가 발생했네요: {e}")

# 사이드바 구성 (대화 초기화 기능)
with st.sidebar:
    st.header("설정")
    st.caption("도움말: 'AAPL 이동평균선과 볼린저밴드 차트'라고 물어보세요!")
    if st.button("대화 기록 초기화 🗑️"):
        st.session_state.chat = model.start_chat(enable_automatic_function_calling=True)
        st.session_state.messages = []
        st.rerun()  # 페이지 새로고침
