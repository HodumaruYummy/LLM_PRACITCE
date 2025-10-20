# ❓ LangChain에서 `AIMessage`는 언제, 왜 import 하나요?

LangChain으로 챗봇을 만들 때 `AIMessage`를 `import`하는 이유는 **대화 기록(History)을 어떻게 관리하느냐**에 따라 달라집니다.

핵심은 **"개발자가 직접 AI의 응답을 리스트에 추가하는가?"** 입니다.

---

## 1. 수동 관리 방식 (예: `langchain_multi_turn.py`)

`while` 루프와 Python `list`를 사용해 대화 기록을 **직접** 관리하는 방식입니다.

```python
# (예: langchain_multi_turn.py)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

llm = ...
messages = [SystemMessage(content="...")] # 1. 리스트 생성

while True:
    user_input = input("사용자: ")
    messages.append(HumanMessage(user_input)) # 2. 사용자 메시지 추가

    ai_response = llm.invoke(messages) # 3. AI 응답 받기
    
    messages.append(ai_response) # 4. AI 응답 추가
    
    print("AI:" + ai_response.content)