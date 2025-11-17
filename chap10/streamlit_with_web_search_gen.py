import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os

# --- [수정] Tavily 검색 도구 import ---
from langchain_community.tools.tavily_search import TavilySearchResults

# --- .env 파일에서 API 키 로드 ---
load_dotenv()
# ------------------------------------


# --- .env 또는 환경변수에서 API 키 로드 ---
google_api_key = os.getenv("GOOGLE_API_KEY")
# --- [추가] Tavily API 키 로드 ---
tavily_api_key = os.getenv("TAVILY_API_KEY")

if not google_api_key:
    st.info("Google API 키(.env 또는 환경 변수)가 설정되지 않았습니다. (GOOGLE_API_KEY)")
    st.stop()

# --- [추가] Tavily 키 확인 ---
if not tavily_api_key:
    st.info("Tavily API 키(.env 또는 환경 변수)가 설정되지 않았습니다. (TAVILY_API_KEY)")
    st.stop()
# ------------------------------------------

# --- 모델 초기화: gemini-2.5-flash (변경 없음) ---
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=google_api_key,
    api_version="v1"
)
# ---------------------------------

# --- 도구 함수 정의 ---

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
    
# --- [수정] get_web_search 함수를 Tavily 버전으로 교체 ---
@tool
def get_web_search(query: str) -> str:
    """
    Tavily를 사용하여 웹 검색을 수행하는 함수.
    'search_period' 인자는 받지 않습니다.
    
    Args:
        query (str): 검색어

    Returns:
        str: 검색 결과 (Snippet, Title, URL 형식)
    """
    print('-------- TAVILY WEB SEARCH --------')
    print(query)

    # Tavily 검색 도구 초기화 (k=5: 5개의 결과 요청)
    search = TavilySearchResults(
        k=5, 
        tavily_api_key=tavily_api_key # API 키 명시적 전달
    ) 
    
    try:
        # Tavily는 [ {'url': ..., 'content': ...}, ... ] 형식의 딕셔너리 리스트를 반환
        docs = search.invoke(query)
        
        results_str_list = []
        for doc in docs:
            snippet = doc.get('content', '내용 없음')
            title = doc.get('title', '제목 없음')
            url = doc.get('url', '출처 없음')
            results_str_list.append(f"Snippet: {snippet}\nTitle: {title}\nURL: {url}")
            
        return "\n\n;\n\n".join(results_str_list)

    except Exception as e:
        print(f"Tavily 검색 오류: {e}")
        return f"검색 중 오류가 발생했습니다: {e}"
# --- DuckDuckGo 버전의 get_web_search는 완전히 삭제 ---


# --- [수정] 도구 바인딩 (한 번만 정의) ---
tools = [get_current_time, get_web_search]
tool_dict = {
    "get_current_time": get_current_time, 
    "get_web_search": get_web_search
}

llm_with_tools = llm.bind_tools(tools)
# ---------------------------------


# 사용자의 메시지 처리하기 위한 함수 (원본과 동일, 변경 없음)
def get_ai_response(messages):
    response_stream = llm_with_tools.stream(messages)
    
    full_response = None
    final_text_content = "" # 최종 텍스트 답변을 누적

    for chunk in response_stream:
        if chunk.content:
            yield chunk.content
            final_text_content += chunk.content
        
        if full_response is None:
            full_response = chunk
        else:
            full_response += chunk

    if full_response and full_response.tool_calls:
        st.session_state.messages.append(full_response)
        
        tool_outputs = []
        
        for tool_call in full_response.tool_calls:
            selected_tool = tool_dict[tool_call['name']]
            
            try:
                # 모델이 Tavily 도구 명세에 따라 {'query': '...'}만 전달할 것임
                tool_output = selected_tool.invoke(tool_call['args'])
            except Exception as e:
                tool_output = f"Tool Error: {e}"
            
            print(f"Tool: {tool_call['name']}, Args: {tool_call['args']}, Output: {tool_output}")

            tool_outputs.append(
                ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call['id']
                )
            )

        for msg in tool_outputs:
            st.chat_message("tool").write(msg.content)
        st.session_state.messages.extend(tool_outputs)
        
        for chunk_content in get_ai_response(st.session_state.messages):
            yield chunk_content
            
    elif final_text_content:
        pass


# Streamlit 앱
st.title("💬 Google Gemini + Tavily Search") # (제목 수정)

# 스트림릿 session_state에 메시지 저장 (변경 없음)
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        SystemMessage("너는 사용자를 돕기 위해 최선을 다하는 인공지능 봇이다. "), 
        AIMessage("무엇을 알고 싶니?")
    ]

# 스트림릿 화면에 메시지 출력 (원본과 동일, 변경 없음)
for msg in st.session_state.messages:
    if msg.content:
        if isinstance(msg, SystemMessage):
            st.chat_message("system").write(msg.content)
        elif isinstance(msg, AIMessage):
            if not msg.tool_calls:
                st.chat_message("assistant").write(msg.content)
        elif isinstance(msg, HumanMessage):
            st.chat_message("user").write(msg.content)
        elif isinstance(msg, ToolMessage):
            st.chat_message("tool").write(f"Tool Output:\n```\n{msg.content}\n```")

# 사용자 입력 처리 (원본과 동일, 변경 없음)
if prompt := st.chat_input():
    st.chat_message("user").write(prompt)
    st.session_state.messages.append(HumanMessage(prompt))

    response_generator = get_ai_response(st.session_state["messages"])
    result = st.chat_message("assistant").write_stream(response_generator)
    
    if result:
        st.session_state["messages"].append(AIMessage(result))