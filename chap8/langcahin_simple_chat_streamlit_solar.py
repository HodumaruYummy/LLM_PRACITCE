import streamlit as st
import os
from dotenv import load_dotenv

# 1. Upstage (OpenAI 호환) 모듈 임포트
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from datetime import datetime
import pytz

# --- API 키 설정 ---
load_dotenv()
upstage_api_key = os.getenv("Solar_api_key")

# (Colab 용 주석)
# from google.colab import userdata
# upstage_api_key = userdata.get('Solar_api_key')
# --------------------

if not upstage_api_key:
    st.error("Solar_api_key가 설정되지 않았습니다. .env 파일을 확인하거나 Colab/Streamlit secrets에 키를 설정해주세요.")
    st.stop()

# 2. 모델 초기화 (Upstage API 사용)
llm = ChatOpenAI(
    model="solar-pro2",
    api_key=upstage_api_key,
    base_url="https://api.upstage.ai/v1"
)

# 3. 도구 함수 정의
@tool
def get_current_time(timezone: str, location: str) -> str:
    """현재 시각을 반환하는 함수."""
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        result = f'{timezone} ({location}) 현재시각 {now}'
        print(result)
        return result
    except pytz.UnknownTimeZoneError:
        return f"알 수 없는 타임존: {timezone}"

# 4. 도구 바인딩
tools = [get_current_time]
tool_dict = {"get_current_time": get_current_time}

llm_with_tools = llm.bind_tools(tools)

# 5. 메시지 처리 함수
def get_ai_response(messages):
    response = llm_with_tools.stream(messages) # ① 
    
    gathered = None # ②
    for chunk in response:
        yield chunk
        
        if gathered is None: #  ③
            gathered = chunk
        else:
            gathered += chunk

    if gathered.tool_calls:
        st.session_state.messages.append(gathered)
        
        for tool_call in gathered.tool_calls:
            selected_tool = tool_dict[tool_call['name']]
            
            # (변경) 랭체인 v0.2.x+ 표준 방식 (Pydantic/일반 함수 겸용)
            tool_msg = selected_tool.invoke(tool_call['args']) 
            
            print(tool_msg, type(tool_msg))
            
            st.session_state.messages.append(ToolMessage(content=str(tool_msg), tool_call_id=tool_call['id']))
            
        for chunk in get_ai_response(st.session_state.messages):
            yield chunk

# --- Streamlit 앱 ---
st.title("💬 챗봇 (Upstage + LangChain Tools)")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        SystemMessage(content="너는 사용자를 돕기 위해 최선을 다하는 인공지능 봇이다. "), 
        AIMessage(content="How can I help you?")
    ]

# 6. 스트림릿 화면에 메시지 출력
for msg in st.session_state.messages:
    if isinstance(msg, SystemMessage):
        pass # 시스템 메시지는 UI에 표시 X
    elif isinstance(msg, AIMessage):
        st.chat_message("assistant").write(msg.content)
    elif isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    elif isinstance(msg, ToolMessage):
        # --- (오류 수정) ---
        # f-string을 한 줄로 합쳤습니다.
        st.chat_message("tool").write(f"Tool (get_current_time): {msg.content}")
        # ---------------------

# 사용자 입력 처리
if prompt := st.chat_input():
    st.chat_message("user").write(prompt) # 사용자 메시지 출력
    st.session_state.messages.append(HumanMessage(content=prompt)) # 사용자 메시지 저장

    response = get_ai_response(st.session_state["messages"])
    
    result = st.chat_message("assistant").write_stream(response) # AI 메시지 출력
    st.session_state.messages.append(AIMessage(content=result)) # AI 메시지 저장