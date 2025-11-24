import os
from datetime import datetime
from typing import List
from typing_extensions import TypedDict

# 환경 변수 로드 (.env 파일에 GOOGLE_API_KEY 설정 필요)
from dotenv import load_dotenv
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    raise ValueError("환경 변수 'GOOGLE_API_KEY'를 설정해주세요. (.env 파일 확인)")

# LangChain / LangGraph 관련 임포트
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI # Gemini용
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage
from langchain_core.prompts import PromptTemplate

# 사용자 정의 유틸리티 (파일이 존재해야 함)
try:
    from utils import save_state 
except ImportError:
    # utils가 없을 경우를 대비한 더미 함수 (실행 에러 방지용)
    def save_state(path, state):
        pass

# 현재 폴더 경로 찾기
filename = os.path.basename(__file__) 
absolute_path = os.path.abspath(__file__) 
current_path = os.path.dirname(absolute_path) 

# 모델 초기화 (Gemini)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", # 또는 gemini-1.5-flash
    temperature=0
)

# 상태 정의
class State(TypedDict):
    messages: List[AnyMessage | str]

# 사용자와 대화할 노드(agent): communicator
def communicator(state: State):
    print("\n\n============ COMMUNICATOR ============")

    # 시스템 프롬프트 정의
    communicator_system_prompt = PromptTemplate.from_template(
        """
        너는 책을 쓰는 AI팀의 커뮤니케이터로서, 
        AI팀의 진행상황을 사용자에게 보고하고, 사용자의 의견을 파악하기 위한 대화를 나눈다. 

        messages: {messages}
        """
    )

    # 시스템 프롬프트와 모델을 연결
    system_chain = communicator_system_prompt | llm

    # 상태에서 메시지를 가져옴
    messages = state["messages"]

    # 입력값 정의
    inputs = {"messages": messages}

    # 스트림되는 메시지를 출력하면서, gathered에 모으기
    gathered = None

    print('\nAI\t: ', end='')
    for chunk in system_chain.stream(inputs):
        print(chunk.content, end='')

        if gathered is None:
            gathered = chunk
        else:
            gathered += chunk

    messages.append(gathered)

    return {"messages": messages}

# 상태 그래프 정의
graph_builder = StateGraph(State)

# Nodes
graph_builder.add_node("communicator", communicator)

# Edges
graph_builder.add_edge(START, "communicator")
graph_builder.add_edge("communicator", END)

graph = graph_builder.compile()

# 이미지 저장 (선택 사항)
try:
    graph.get_graph().draw_mermaid_png(output_file_path=absolute_path.replace('.py', '.png'))
except Exception:
    pass # grandalf 등 의존성 문제시 패스

# 상태 초기화
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

while True:
    user_input = input("\nUser\t: ").strip()

    if user_input.lower() in ['exit', 'quit', 'q']:
        print("Goodbye!")
        break
    
    state["messages"].append(HumanMessage(content=user_input))
    state = graph.invoke(state)

    print('\n------------------------------------ MESSAGE COUNT\t', len(state["messages"]))

    save_state(current_path, state) # 현재 state 내용 저장