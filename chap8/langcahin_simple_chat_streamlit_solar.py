import streamlit as st
import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from datetime import datetime
import pytz

# --- API 키 설정 ---
load_dotenv()
upstage_api_key = os.getenv("Solar_api_key")
if not upstage_api_key:
    st.error("Solar_api_key가 설정되지 않았습니다.")
    st.stop()
# --------------------

# 1. 모델 초기화 (Upstage API 사용)
llm = ChatOpenAI(
    model="solar-pro2",
    api_key=upstage_api_key,
    base_url="https://api.upstage.ai/v1"
)

# 2. 도구 함수 정의
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

# 3. 도구 바인딩
tools = [get_current_time]
tool_dict = {"get_current_time": get_current_time}
llm_with_tools = llm.bind_tools(tools)

# 4. (유지) Upstage는 재귀 스트리밍이 잘 작동하므로,
# `get_ai_response` 함수를 그대로 사용합니다.
def get_ai_response(messages):
    response = llm_with_tools.stream(messages) 
    
    gathered = None
    for chunk in response:
        yield chunk
        if gathered is None: gathered = chunk
        else: gathered += chunk

    if gathered.tool_calls:
        st.session_state.messages.append(gathered)
        
        for tool_call in gathered.tool_calls:
            selected_tool = tool_dict[tool_call['name']]
            tool_msg = selected_tool.invoke(tool_call['args']) 
            
            st.session_state.messages.append(ToolMessage(content=str(tool_msg), tool_call_id=tool_call['id']))
            
        for chunk in get_ai_response(st.session_state.messages):
            yield chunk

# --- Streamlit 앱 ---
st.title("💬 챗봇 (Upstage + LangChain Tools)")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        SystemMessage(content="너는 사용자를 돕는 AI 봇이다."), 
        AIMessage(content="How can I help you?")
    ]

# 5. 메시지 출력 (SyntaxError 수정)
for msg in st.session_state.messages:
    if isinstance(msg, SystemMessage): pass
    elif isinstance(msg, AIMessage): st.chat_message("assistant").write(msg.content)
    elif isinstance(msg, HumanMessage): st.chat_message("user").write(msg.content)
    elif isinstance(msg, ToolMessage):
        st.chat_message("tool").write(f"Tool (get_current_time): {msg.content}")

# --- 6. (원본 로직 유지) 사용자 입력 처리 ---
if prompt := st.chat_input():
    st.chat_message("user").write(prompt)
    st.session_state.messages.append(HumanMessage(content=prompt))

    response = get_ai_response(st.session_state.messages)
    
    # 💥💥💥
    # Upstage(OpenAI)는 이 'result'가 올바른 문자열(string)이므로
    # Pydantic 오류가 발생하지 않습니다.
    # 💥💥💥
    result = st.chat_message("assistant").write_stream(response)
    st.session_state.messages.append(AIMessage(content=result))