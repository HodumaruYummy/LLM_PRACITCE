import streamlit as st
import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from datetime import datetime
import pytz

# --- API 키 설정 ---
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
if not google_api_key:
    st.error("GOOGLE_API_KEY가 설정되지 않았습니다.")
    st.stop()
# --------------------

# 1. 모델 초기화 (요청하신 gemini-2.5-flash 사용)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=google_api_key)

# 2. 도구 함수 정의 (원본과 동일)
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

# 3. 도구 바인딩 (원본과 동일)
tools = [get_current_time]
tool_dict = {"get_current_time": get_current_time}
llm_with_tools = llm.bind_tools(tools)


# 4. (신규) 스트리밍 및 메시지 조립을 위한 헬퍼 함수
def stream_and_assemble_response(messages):
    """
    LLM 응답을 스트리밍하고, 전체 청크(chunk)를 조립하여
    (스트리밍 제너레이터, 조립된 메시지)를 반환합니다.
    """
    stream = llm_with_tools.stream(messages)
    
    # 청크를 저장할 리스트
    stream_chunks = []
    
    # UI 스트리밍을 위한 제너레이터
    def generator_for_ui():
        for chunk in stream:
            stream_chunks.append(chunk) # 청크 저장
            if chunk.content:
                yield chunk.content # UI에는 문자열 content만 전달
    
    # 조립된 메시지를 반환하기 위한 함수
    def get_assembled_message():
        if not stream_chunks:
            return AIMessage(content="") # 빈 응답 처리
            
        # 모든 청크를 더하여 완전한 AIMessage 객체로 만듦
        assembled_message = stream_chunks[0]
        for chunk in stream_chunks[1:]:
            assembled_message += chunk
        return assembled_message

    return generator_for_ui(), get_assembled_message

# --- Streamlit 앱 ---
st.title("💬 챗봇 (Gemini + LangChain Tools)")

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
        # f-string을 한 줄로 수정
        st.chat_message("tool").write(f"Tool (get_current_time): {msg.content}")

# --- 6. (로직 전면 수정) 사용자 입력 처리 ---
if prompt := st.chat_input():
    st.chat_message("user").write(prompt)
    st.session_state.messages.append(HumanMessage(content=prompt))

    # 1. 첫 번째 응답 (스트리밍)
    ui_container = st.chat_message("assistant")
    stream_gen, get_message_func = stream_and_assemble_response(st.session_state.messages)
    
    # UI에 스트리밍 실행 (write_stream의 반환 값은 사용 안 함!)
    ui_container.write_stream(stream_gen)
    
    # 스트리밍이 끝난 후, 조립된 메시지 가져오기
    gathered_message = get_message_func()
    st.session_state.messages.append(gathered_message) # Pydantic 오류 해결!

    # 2. 도구 호출이 있는지 확인
    if gathered_message.tool_calls:
        # 3. 도구 실행
        for tool_call in gathered_message.tool_calls:
            selected_tool = tool_dict[tool_call['name']]
            # Pydantic/일반 함수 호환을 위해 'args' 사용
            tool_msg_content = selected_tool.invoke(tool_call['args'])
            
            tool_message = ToolMessage(content=str(tool_msg_content), tool_call_id=tool_call['id'])
            st.session_state.messages.append(tool_message)
            # 도구 실행 결과도 UI에 표시
            st.chat_message("tool").write(f"Tool ({tool_call['name']}): {tool_msg_content}")
        
        # 4. 도구 실행 결과를 포함하여 *최종* 응답 (스트리밍)
        final_ui_container = st.chat_message("assistant")
        final_stream_gen, get_final_message_func = stream_and_assemble_response(st.session_state.messages)
        
        final_ui_container.write_stream(final_stream_gen)
        
        # 최종 메시지 저장
        final_gathered_message = get_final_message_func()
        st.session_state.messages.append(final_gathered_message)