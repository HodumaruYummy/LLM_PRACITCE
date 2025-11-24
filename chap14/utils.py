import os
import json

def save_state(current_path, state):
    """
    현재 대화 상태(state)를 JSON 파일로 저장하는 함수입니다.
    LangChain의 메시지 객체들을 텍스트 형태로 변환하여 'data/state.json'에 기록합니다.
    """
    
    # 1. 데이터를 저장할 'data' 폴더가 존재하는지 확인
    # f-string을 사용하여 현재 경로(current_path) 하위의 data 폴더 경로를 지정
    if not os.path.exists(f"{current_path}/data"):
        os.makedirs(f"{current_path}/data") # 폴더가 없으면 새로 생성
    
    # 저장할 데이터를 담을 빈 딕셔너리 초기화
    state_dict = {}

    # 2. 메시지 객체 변환 (직렬화)
    # state["messages"] 리스트에는 LangChain의 객체(HumanMessage, AIMessage 등)가 들어있습니다.
    # 이 객체들은 바로 JSON으로 저장이 불가능하므로, 문자열 정보만 추출합니다.
    # (클래스이름, 메시지내용) 형태의 튜플 리스트로 변환합니다.
    # 예: [('HumanMessage', '안녕'), ('AIMessage', '안녕하세요')]
    messages = [(m.__class__.__name__, m.content) for m in state["messages"]]
    
    # 변환된 메시지 리스트를 딕셔너리에 담기
    state_dict["messages"] = messages
    
    # 3. JSON 파일로 쓰기 (저장)
    # 'w' 모드로 파일을 열어 내용을 덮어씁니다. encoding='utf-8'은 한글 처리를 위해 필수입니다.
    with open(f"{current_path}/data/state.json", "w", encoding='utf-8') as f:
        json.dump(
            state_dict, 
            f, 
            indent=4,           # 들여쓰기를 4칸으로 설정하여 사람이 읽기 편하게 저장
            ensure_ascii=False  # True일 경우 한글이 유니코드 문자(\uXXXX)로 깨져 보이므로 False로 설정
        )