# Chatbot (Streamlit + LangChain Tools)

이 저장소는 **Streamlit** UI 위에서 **LangChain** 도구 호출(🛠️ `@tool`)과 **스트리밍 응답**을 사용하는 두 가지 예제를 제공합니다.

- **Gemini 버전**: `langcahin_simple_chat_streamlit_gen.py` — `ChatGoogleGenerativeAI` 사용, `GOOGLE_API_KEY` 필요 fileciteturn0file0
- **Upstage(SOLAR) 버전**: `langcahin_simple_chat_streamlit_solar.py` — OpenAI 호환 `ChatOpenAI` 사용, `Solar_api_key` 필요 fileciteturn0file1
- **CLI 멀티턴 예제**: `langchain_multiturn_gen.py` — 콘솔에서 대화 이력 직접 관리(수동 방식) fileciteturn0file3
- **AIMessage 사용 가이드**: `AImessage.md` — 언제 `AIMessage`를 import/사용하는지에 대한 설명 문서 fileciteturn0file2

---

## 1) 주요 기능

### ✅ 공통
- **LangChain Tools**: `@tool` 데코레이터로 등록된 `get_current_time(timezone, location)` 도구를 LLM이 필요 시 자동 호출합니다. 스트리밍 중간에도 *도구 호출 → 결과 반영 → 최종 답변* 흐름을 처리합니다. fileciteturn0file0 fileciteturn0file1
- **대화 이력 관리**: `SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage`를 사용하여 메시지를 리스트에 보관합니다. fileciteturn0file0 fileciteturn0file1
- **스트리밍 응답**: 모델 응답을 청크 단위로 UI에 출력하고, 스트림이 끝난 뒤 **청크를 병합**해 하나의 `AIMessage`로 세션 이력에 저장합니다. fileciteturn0file0

### 🟦 Gemini (Google) 버전
- 모델: `gemini-2.5-flash`
- 바인딩: `llm.bind_tools([get_current_time])`
- 스트리밍: `llm_with_tools.stream(messages)`를 제너레이터로 UI에 전송, 종료 후 `AIMessage` 병합 저장. fileciteturn0file0

### 🟧 Upstage (Solar) 버전
- 모델: `solar-pro2` (`ChatOpenAI` + `base_url="https://api.upstage.ai/v1"`)
- OpenAI 호환 API를 통해 동일한 도구 호출/스트리밍 패턴을 사용. fileciteturn0file1

### 🖥️ CLI 멀티턴
- 콘솔에서 `while True` 루프로 사용자 입력을 받아 `messages` 리스트를 수동 갱신하고 `llm.invoke(messages)`로 응답. `exit` 입력 시 종료. fileciteturn0file3
- 왜 `AIMessage`를 직접 append 해야 하는지에 대한 배경은 `AImessage.md` 참고. fileciteturn0file2

---

## 2) 빠른 시작 (Quick Start)

### 2-1. 환경 변수(.env)
루트에 `.env` 파일을 만들고 필요한 키를 설정하세요.

**Gemini 사용 시**
```env
GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY
```

**Upstage(SOLAR) 사용 시**
```env
Solar_api_key=YOUR_UPSTAGE_SOLAR_API_KEY
```

### 2-2. 설치
```bash
pip install -r requirements.txt
```

### 2-3. 실행

**Gemini (Streamlit)**
```bash
streamlit run langcahin_simple_chat_streamlit_gen.py
```

**Upstage (Streamlit)**
```bash
streamlit run langcahin_simple_chat_streamlit_solar.py
```

**CLI 멀티턴 (콘솔)**
```bash
python langchain_multiturn_gen.py
```

---

## 3) 파일별 상세

### `langcahin_simple_chat_streamlit_gen.py` (Gemini)
- `.env`에서 `GOOGLE_API_KEY` 로드 → 모델 `gemini-2.5-flash` 초기화
- `@tool get_current_time()` 등록 후 `llm.bind_tools(...)`로 바인딩
- 응답 스트리밍과 동시에 **청크 병합** → `AIMessage` 저장
- 도구 호출 발생 시 `ToolMessage` 저장 및 UI 출력, 이후 **최종 답변** 스트리밍
fileciteturn0file0

### `langcahin_simple_chat_streamlit_solar.py` (Upstage / Solar)
- `.env`에서 `Solar_api_key` 로드, `ChatOpenAI`에 `base_url` 지정
- `@tool get_current_time()` 동일 등록 및 바인딩
- `llm_with_tools.stream(messages)`를 순회하며 **청크 누적(gathered) → 도구 호출 처리 → 재귀로 최종 응답 생성** 로직 구현
fileciteturn0file1

### `langchain_multiturn_gen.py` (CLI)
- `messages = [SystemMessage(...)]`로 시작
- 사용자 입력을 `HumanMessage`로 추가 → `llm.invoke(messages)` → 반환된 `AIMessage`를 다시 리스트에 추가
- `exit` 입력 시 루프 종료
fileciteturn0file3

### `AImessage.md`
- 수동 기록 방식과 LangChain의 메시지 객체(`AIMessage`, `HumanMessage`, `SystemMessage`)의 사용 시점/이유 정리
fileciteturn0file2

---

## 4) 주의 및 팁

- **도구 시그니처**: `@tool` 함수에 다중 파라미터를 쓰면 자동 스키마가 다소 복잡해질 수 있습니다. 필요 시 Pydantic 입력 모델로 감싸 통일해도 좋습니다.
- **타임존**: `get_current_time`는 `pytz`의 타임존 문자열을 그대로 사용하므로 올바른 IANA 타임존을 입력하세요(예: `Asia/Seoul`). fileciteturn0file0 fileciteturn0file1
- **스트리밍 병합**: 스트리밍 후 **청크를 누적/병합**해 `AIMessage`로 저장해야 이후 라운드에서 도구 호출 여부 판단 및 대화 맥락 유지가 안정적입니다. fileciteturn0file0
- **키 누락 처리**: 환경 변수가 없으면 Streamlit 앱은 즉시 종료하며 오류 메시지를 표시합니다. fileciteturn0file0 fileciteturn0file1

---

## 5) 확장 아이디어

- `@tool`에 외부 API(예: 주가, 날씨) 연동 추가
- 메시지 영속화(예: SQLite/FAISS) 및 사용자별 히스토리 분리
- 멀티에이전트/라우팅(질문 유형에 따라 모델 또는 도구 선택)

---

## 6) 라이선스
해당 예제 코드는 교육/연구 목적으로 자유롭게 수정/확장할 수 있습니다.
