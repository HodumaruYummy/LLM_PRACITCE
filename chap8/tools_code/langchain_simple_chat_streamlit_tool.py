import streamlit as st
import os
from dotenv import load_dotenv

# langchain-google-genai에서 Gemini 모델 클래스를 가져옵니다.
from langchain_google_genai import ChatGoogleGenerativeAI
# 랭체인의 표준 메시지 타입들(System, Human, AI, Tool)을 가져옵니다.
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# 1. ⭐️ (중요) 별도로 정의한 tools.py 파일에서
#    도구 리스트(all_tools)와 도구 딕셔너리(tool_dict)를 가져옵니다.
from tools import all_tools, tool_dict

# --- API 키 설정 ---
# .env 파일에 정의된 환경 변수를 로드합니다.
load_dotenv()
# 환경 변수에서 "GOOGLE_API_KEY" 값을 읽어옵니다.
google_api_key = os.getenv("GOOGLE_API_KEY")

# 만약 API 키가 없다면, (Colab/Streamlit Secrets에도 없다면)
if not google_api_key:
    # 에러 메시지를 UI에 표시하고
    st.error("GOOGLE_API_KEY가 설정되지 않았습니다.")
    # 앱 실행을 중지합니다.
    st.stop()
# --------------------

# 2. 모델 초기화 (요청하신 gemini-2.5-flash 모델 사용)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=google_api_key)

# 3. ⭐️ (중요) 초기화된 LLM 객체에 
#    tools.py에서 가져온 도구(함수)들을 연결(바인딩)합니다.
llm_with_tools = llm.bind_tools(all_tools)

# 4. ‼️‼️ (핵심 로직) Gemini의 'ValidationError'를 우회하기 위한 헬퍼 함수
# 이 함수는 두 가지 '결과물'을 반환합니다:
# (1) UI 스트리밍에 사용할 제너레이터 (generator_for_ui)
# (2) 대화 기록에 저장할 완성된 AIMessage 객체를 반환하는 함수 (get_assembled_message)
def stream_and_assemble_response(messages):
    
    # (내부 1) 랭체인 모델을 스트리밍 모드로 호출합니다. (결과는 제너레이터)
    stream = llm_with_tools.stream(messages)
    
    # (내부 2) LLM이 생성한 청크(AIMessageChunk 객체)들을 저장할 빈 리스트입니다.
    stream_chunks = []
    
    # (내부 3) Streamlit의 'write_stream'에 전달할 *순수 텍스트 내용물* 제너레이터입니다.
    def generator_for_ui():
        # (내부 4) LLM 응답 스트림을 순회합니다.
        for chunk in stream:
            # (내부 5) ‼️ 청크 객체 *자체*를 리스트에 저장합니다. (나중에 조립하기 위함)
            stream_chunks.append(chunk)
            # (내부 6) ‼️ 청크의 'content' 부분(문자열)만 UI 스트리밍용으로 반환(yield)합니다.
            if chunk.content:
                yield chunk.content
    
    # (내부 7) 스트리밍이 모두 끝난 후, 저장된 청크들을 조립(assemble)하는 함수입니다.
    def get_assembled_message():
        # (내부 8) 만약 스트리밍된 청크가 없다면 (예: 오류), 빈 AI 메시지를 반환합니다.
        if not stream_chunks: return AIMessage(content="")
        
        # (내부 9) 첫 번째 청크를 기준으로...
        assembled_message = stream_chunks[0]
        # (내부 10) 나머지 모든 청크를 덧셈 연산(결합)하여 하나의 완전한 AIMessage 객체로 만듭니다.
        for chunk in stream_chunks[1:]:
            assembled_message += chunk
            
        # (내부 11) ‼️ Pydantic 유효성 검사를 통과하는, 잘 조립된 AIMessage 객체를 반환합니다.
        return assembled_message

    # (내부 12) 헬퍼 함수는 이 두 가지 내부 함수/제너레이터를 튜플로 반환합니다.
    return generator_for_ui(), get_assembled_message

# --- Streamlit UI ---

# 웹 앱의 제목(타이틀)을 설정합니다.
st.title("💬 챗봇 (Gemini + LangChain Tools)")

# st.session_state는 Streamlit이 세션 간에 데이터를 유지하는 저장소입니다.
# "messages" 키가 세션에 없다면 (즉, 앱을 처음 실행했거나 새로고침했다면)
if "messages" not in st.session_state:
    # 대화 기록(messages)을 리스트로 초기화합니다.
    st.session_state["messages"] = [
        SystemMessage(content="너는 사용자를 돕는 AI 봇이다."), 
        AIMessage(content="무엇을 도와드릴까요?")
    ]

# 5. (UI) 세션에 저장된 모든 대화 기록을 순회합니다.
for msg in st.session_state.messages:
    # 메시지 타입에 따라 UI에 표시합니다.
    if isinstance(msg, SystemMessage): pass # 시스템 메시지는 UI에 표시하지 않음
    elif isinstance(msg, AIMessage): st.chat_message("assistant").write(msg.content)
    elif isinstance(msg, HumanMessage): st.chat_message("user").write(msg.content)
    elif isinstance(msg, ToolMessage):
        # ‼️ (오류 수정) f-string이 한 줄로 끝나도록 수정 (SyntaxError 방지)
        st.chat_message("tool").write(f"Tool Result: {msg.content}")

# --- 6. (메인 로직) 사용자 입력 처리 ---

# 'st.chat_input()'은 사용자가 입력한 채팅 메시지를 받습니다.
# (사용자가 엔터를 치면 'prompt' 변수에 문자열이 할당되고, if문이 True가 됨)
if prompt := st.chat_input():
    # (로직 1) 사용자가 입력한 메시지를 'user' 역할로 UI에 즉시 표시합니다.
    st.chat_message("user").write(prompt)
    
    # (로직 2) 사용자의 메시지를 HumanMessage 객체로 변환하여 대화 기록(session_state)에 추가합니다.
    st.session_state.messages.append(HumanMessage(content=prompt))

    # (로직 3) AI 응답을 스트리밍으로 표시할 빈 UI 영역(컨테이너)을 확보합니다.
    ui_container = st.chat_message("assistant")
    
    # (로직 4) ‼️ 헬퍼 함수를 호출합니다. (현재까지의 대화 기록을 전달)
    #        (1) stream_gen: UI 스트리밍용 제너레이터
    #        (2) get_message_func: 스트리밍 끝난 후 조립된 AIMessage를 반환할 함수
    stream_gen, get_message_func = stream_and_assemble_response(st.session_state.messages)
    
    # (로직 5) ‼️ UI 컨테이너에 스트리밍 제너레이터(stream_gen)를 연결해 화면에 실시간 출력합니다.
    # ‼️ (핵심) write_stream의 반환 값(result)은 의도적으로 *사용하지 않습니다* (버립니다).
    #        Gemini 사용 시 이 반환 값이 Pydantic 'ValidationError'의 원인이 됩니다.
    ui_container.write_stream(stream_gen)
    
    # (로직 6) ‼️ 스트리밍이 모두 끝난 후, 헬퍼 함수가 반환한 두 번째 함수(get_message_func)를 호출합니다.
    #        이 변수에는 조립이 완료된 'AIMessage' 객체가 들어갑니다.
    gathered_message = get_message_func()
    
    # (로직 7) ‼️ (Pydantic 오류 해결)
    #        'result' 변수 대신, '조립된(gathered)' AIMessage 객체를 대화 기록에 저장합니다.
    st.session_state.messages.append(gathered_message)

    # (로직 8) ‼️ 방금 받은 AI 응답(gathered_message)에 도구 호출(tool_calls)이 포함되어 있는지 확인합니다.
    if gathered_message.tool_calls:
        
        # (로직 9) 호출해야 할 도구들을 순회합니다. (여러 개일 수 있음)
        for tool_call in gathered_message.tool_calls:
            # (로직 10) 도구 이름(문자열)을 사용해 `tool_dict`에서 실제 Python 함수를 찾아옵니다.
            selected_tool = tool_dict[tool_call['name']]
            
            # (로직 11) ‼️ LLM이 생성한 'args'를 넘겨주어 실제 Python 함수를 실행(invoke)합니다.
            #          (Pydantic 모델/일반 함수 모두 이 방식 'args'로 호환됩니다)
            tool_msg_content = selected_tool.invoke(tool_call['args'])
            
            # (로직 12) 도구 실행 결과를 ToolMessage 객체로 포장합니다. (tool_call_id를 반드시 포함)
            tool_message = ToolMessage(content=str(tool_msg_content), tool_call_id=tool_call['id'])
            
            # (로직 13) 도구 실행 결과 메시지를 대화 기록에 추가합니다.
            st.session_state.messages.append(tool_message)
            
            # (로직 14) 도구 실행 결과를 UI에도 표시합니다. (사용자 확인용)
            st.chat_message("tool").write(f"Tool ({tool_call['name']}): {tool_msg_content}")
        
        # (로직 15) ‼️ 도구 실행 결과를 바탕으로 한 *최종 답변*을 표시할 새 UI 컨테이너를 확보합니다.
        final_ui_container = st.chat_message("assistant")
        
        # (로직 16) ‼️ 헬퍼 함수를 *다시 호출*합니다. 
        #           (이제 messages에는 도구 실행 결과(ToolMessage)까지 포함되어 있습니다)
        final_stream_gen, get_final_message_func = stream_and_assemble_response(st.session_state.messages)
        
        # (로직 17) 최종 답변을 UI에 스트리밍합니다.
        final_ui_container.write_stream(final_stream_gen)
        
        # (로직 18) 최종 답변 메시지를 조립합니다.
        final_gathered_message = get_final_message_func()
        
        # (로직 19) 최종 답변 메시지를 대화 기록에 저장합니다.
        st.session_state.messages.append(final_gathered_message)