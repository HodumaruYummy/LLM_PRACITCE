import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime
from typing import List
from typing_extensions import TypedDict

# 환경 변수 로드
# API 키는 API 호출 시 인증을 위해 필수적입니다.
from dotenv import load_dotenv
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# LangGraph 및 LangChain 관련 라이브러리 임포트
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI # 구글 Gemini 모델 사용
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser

# 사용자 정의 유틸리티 모듈 임포트 (파일 입출력 관련 함수들)
# utils.py 파일이 같은 디렉토리에 있어야 정상 작동합니다.
try:
    from utils import save_state, get_outline, save_outline 
except ImportError:
    print("경고: utils.py를 찾을 수 없습니다. 더미 함수를 사용합니다.")
    # 파일이 없을 경우 에러를 방지하기 위한 빈 함수 정의
    def save_state(path, state): pass
    def get_outline(path): return "목차 없음"
    def save_outline(path, content): pass

# 현재 실행 중인 파일의 경로 정보 획득
# 추후 데이터 저장(목차, 상태 등)이나 그래프 이미지 저장 경로로 사용됩니다.
filename = os.path.basename(__file__) 
absolute_path = os.path.abspath(__file__) 
current_path = os.path.dirname(absolute_path) 

# 모델 초기화 (Google Gemini)
# temperature=0으로 설정하여 일관성 있는(덜 무작위적인) 답변을 유도합니다.
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", # 사용 모델 지정
    temperature=0
)

# [LangGraph] 상태(State) 정의
# 노드 간에 데이터를 주고받는 공유 메모리 역할을 하는 구조체입니다.
# 여기서는 대화 내역(messages)을 리스트 형태로 저장합니다.
class State(TypedDict):
    messages: List[AnyMessage | str]

# ------------------------------------------------------------------
# 노드 1: 콘텐츠 전략가 (Content Strategist)
# 역할: 사용자의 요구사항을 분석하여 책의 목차(Outline)를 생성하거나 수정합니다.
# ------------------------------------------------------------------
def content_strategist(state: State):
    print("\n\n============ CONTENT STRATEGIST ============")

    # 프롬프트 템플릿 정의: 전략가의 역할과 수행해야 할 작업을 명시
    content_strategist_system_prompt = PromptTemplate.from_template(
        """
        너는 책을 쓰는 AI팀의 콘텐츠 전략가(Content Strategist)로서,
        이전 대화 내용을 바탕으로 사용자의 요구사항을 분석하고, AI팀이 쓸 책의 세부 목차를 결정한다.

        지난 목차가 있다면 그 버전을 사용자의 요구에 맞게 수정하고, 없다면 새로운 목차를 제안한다.

        --------------------------------
        - 지난 목차: {outline}
        --------------------------------
        - 이전 대화 내용: {messages}
        """
    )

    # [LCEL Chain 구성] 프롬프트 -> 모델 -> 문자열 파서
    # StrOutputParser()는 모델의 복잡한 메시지 객체에서 텍스트 내용만 추출합니다.
    content_strategist_chain = content_strategist_system_prompt | llm | StrOutputParser()

    messages = state["messages"]        # 현재까지의 대화 기록 가져오기
    outline = get_outline(current_path) # 파일에 저장된 기존 목차 가져오기

    # 체인에 전달할 입력 변수 설정
    inputs = {
        "messages": messages,
        "outline": outline
    }

    # 모델 실행 및 스트리밍 출력
    # 목차 생성 과정을 실시간으로 보여줍니다.
    gathered = ''
    for chunk in content_strategist_chain.stream(inputs):
        gathered += chunk # 스트리밍된 조각들을 하나의 문자열로 합침
        print(chunk, end='')

    print()

    # 생성된 목차를 파일로 저장 (utils.py의 함수 활용)
    save_outline(current_path, gathered) 

    # 상태(State) 업데이트를 위한 메시지 생성
    # 실제 목차 내용은 너무 길 수 있으므로, "완료되었습니다"라는 시스템 메시지만 대화 기록에 남깁니다.
    content_strategist_message = f"[Content Strategist] 목차 작성 완료"
    print(content_strategist_message)
    messages.append(AIMessage(content=content_strategist_message))

    return {"messages": messages} # 업데이트된 메시지 리스트 반환


# ------------------------------------------------------------------
# 노드 2: 커뮤니케이터 (Communicator)
# 역할: 사용자와 직접 대화하며 진행 상황을 보고하고 의견을 묻습니다.
# ------------------------------------------------------------------
def communicator(state: State):
    print("\n\n============ COMMUNICATOR ============")

    # 프롬프트 템플릿 정의: 사용자와 소통하는 역할
    communicator_system_prompt = PromptTemplate.from_template(
        """
        너는 책을 쓰는 AI팀의 커뮤니케이터로서, 
        AI팀의 진행상황을 사용자에게 보고하고, 사용자의 의견을 파악하기 위한 대화를 나눈다. 

        사용자도 outline(목차)을 이미 보고 있으므로, 다시 출력할 필요는 없다.

        messages: {messages}
        """
    )

    # [LCEL Chain] 프롬프트 -> 모델 (파서 없음: 메시지 객체를 그대로 유지하기 위함)
    system_chain = communicator_system_prompt | llm

    messages = state["messages"]
    inputs = {"messages": messages}

    # 스트리밍 출력 및 응답 수집
    gathered = None
    print('\nAI\t: ', end='')
    for chunk in system_chain.stream(inputs):
        print(chunk.content, end='')

        # 첫 번째 청크면 gathered 초기화, 아니면 이어 붙이기
        if gathered is None:
            gathered = chunk
        else:
            gathered += chunk

    # 완성된 AI 메시지를 대화 기록에 추가
    messages.append(gathered)

    return {"messages": messages}

# ------------------------------------------------------------------
# [LangGraph] 그래프 정의 및 컴파일
# ------------------------------------------------------------------
graph_builder = StateGraph(State) # 상태 그래프 생성

# 노드 추가 (이름, 함수)
graph_builder.add_node("communicator", communicator)
graph_builder.add_node("content_strategist", content_strategist)

# 엣지(흐름) 정의
# 시작 -> 콘텐츠 전략가 -> 커뮤니케이터 -> 종료
graph_builder.add_edge(START, "content_strategist") 
graph_builder.add_edge("content_strategist", "communicator")  
graph_builder.add_edge("communicator", END)

# 그래프 컴파일 (실행 가능한 형태로 변환)
graph = graph_builder.compile()

# 그래프 구조를 이미지로 시각화하여 저장 (mermaid_png 사용)
try:
    graph.get_graph().draw_mermaid_png(output_file_path=absolute_path.replace('.py', '.png'))
except Exception:
    pass

# ------------------------------------------------------------------
# 메인 실행 루프
# ------------------------------------------------------------------

# 초기 상태 설정 (시스템 메시지 주입)
state = State(
    messages = [
        SystemMessage(
            content=f"""
            너희 AI들은 사용자의 요구에 맞는 책을 쓰는 작가팀이다.
            사용자가 사용하는 언어로 대화하라.

            현재시각은 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}이다.
            """
        )
    ],
)

# 사용자 입력 반복 루프
while True:
    user_input = input("\nUser\t: ").strip()

    # 종료 조건 확인
    if user_input.lower() in ['exit', 'quit', 'q']:
        print("Goodbye!")
        break
    
    # 사용자 메시지를 상태에 추가
    state["messages"].append(HumanMessage(content=user_input))
    
    # 그래프 실행 (Invoke)
    state = graph.invoke(state)

    print('\n------------------------------------ MESSAGE COUNT\t', len(state["messages"]))

    # 현재 대화 상태를 파일로 백업
    save_state(current_path, state)