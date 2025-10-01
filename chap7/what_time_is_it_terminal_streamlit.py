import google.generativeai as genai
import os
from dotenv import load_dotenv
import streamlit as st

# gemini_tools.py 파일에서 함수와 도구 목록을 가져옵니다.
from gemini_functions import tools

# --- 1. 초기 설정 ---

# 페이지 설정 (가장 먼저 호출되어야 함)
st.set_page_config(
    page_title="품격있는 챗봇 🧐",
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
        temperature=0.7, # temperature: 생성될 텍스트의 무작위성을 조절합니다. (0.0 ~ 1.0)
        # 값이 높을수록 (예: 0.7) 더 창의적이고 다양한 결과가 나오지만, 일관성이 떨어질 수 있습니다.
        # 값이 낮을수록 (예: 0.2) 더 결정론적이고 일관된 결과가 나옵니다.
        top_p=0.95,  # top_p: 확률적 샘플링(nucleus sampling)을 위한 매개변수입니다. (0.0 ~ 1.0)
        # 모델이 다음 단어를 예측할 때, 확률 분포에서 누적 확률이 top_p 값에 도달할 때까지의 단어들만 후보로 고려합니다.
        # 예를 들어 0.95로 설정하면, 가장 확률이 높은 단어들부터 시작하여 누적 확률이 95%가 되는 지점까지의 단어 집합에서 다음 단어를 선택합니다.
        # 이를 통해 확률이 매우 낮은 단어들이 선택되는 것을 방지하여 더 자연스러운 문장을 만듭니다.
        top_k=3,  # top_k: 다음 단어를 선택할 때 고려할 후보 단어의 개수를 제한합니다. (정수)
        # 예를 들어 3으로 설정하면, 모델이 예측한 단어들 중 가장 확률이 높은 3개의 단어 중에서만 다음 단어를 선택합니다.
        # 이를 통해 생성될 텍스트의 범위를 좁혀 더 예측 가능한 결과를 얻을 수 있습니다.
        max_output_tokens=4096,
    ),
    # 사용할 도구(함수)와 시스템 지침 설정
    tools=tools,
    system_instruction="당신은 매우 고상하고 기품있는 대화 상대입니다. 사용자의 질문에 답변할 때, 항상 다채로운 이모지를 사용하여 풍부한 감정을 표현해주세요. 🧐✨"
)

# --- 3. Streamlit 세션 상태 관리 ---

# 세션 상태 초기화
if "chat" not in st.session_state:
    # 모델의 채팅 세션을 시작하고 세션 상태에 저장
    st.session_state.chat = model.start_chat(enable_automatic_function_calling=True)
if "messages" not in st.session_state:
    # 화면에 표시될 메시지 기록을 초기화
    st.session_state.messages = []

# --- 4. Streamlit UI 구성 ---

# 앱 제목 설정
st.title("품격있는 챗봇과 대화하기 🧐")
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
        # Gemini 모델에 사용자 입력을 보내고 응답 받기
        # 자동 함수 호출이 활성화되어 있어, 'get_current_time'이 필요하면 스스로 실행합니다.
        response = st.session_state.chat.send_message(user_input)
        
        # 모델의 응답을 화면에 표시하고 기록에 추가
        with st.chat_message("assistant"):
            st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})

    except Exception as e:
        st.error(f"이런, 오류가 발생했네요: {e}")

# 사이드바 구성 (대화 초기화 기능)
with st.sidebar:
    st.header("설정")
    if st.button("대화 기록 초기화 🗑️"):
        # 세션 상태를 초기화하여 대화를 새로 시작
        st.session_state.chat = model.start_chat(enable_automatic_function_calling=True)
        st.session_state.messages = []
        st.rerun() # 페이지를 새로고침하여 변경사항을 즉시 반영