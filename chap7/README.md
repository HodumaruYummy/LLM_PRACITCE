# 품격있는 Gemini 도구 챗봇 (Streamlit/Terminal)

이 저장소는 **Google Gemini**를 사용해 대화 중 자동으로 **함수(도구)** 를 호출하는 챗봇 예제입니다.  
Streamlit 웹 앱과 터미널(콘솔) 앱 두 가지 형태로 제공되며, `yfinance`를 통한 **주가 조회/추천/히스토리**와 `pytz`를 활용한 **현재 시간** 조회 도구가 포함되어 있습니다.

---

## 구성 파일

- `gemini_functions.py` : Gemini가 호출하는 **도구 함수 모음**
  - `get_current_time(timezone: str)` – 타임존 기준 현재 시간 JSON 반환
  - `get_yf_stock_info(ticker: str)` – 종목 정보
  - `get_yf_stock_history(ticker: str, period: str)` – 종목 가격 히스토리(markdown)
  - `get_yf_recommendations(ticker: str)` – 애널리스트 추천(markdown)
  - `tools = [...]` 로 위 함수들을 Gemini에 **도구**로 등록
- `stock_streamlit.py` : Streamlit 앱 (챗 UI + 자동 함수 호출)
- `what_time_is_it_terminal.py` : 터미널(콘솔)에서 동작하는 챗봇
- `what_time_is_it_terminal_streamlit.py` : Streamlit 앱 (챗 UI + 자동 함수 호출, 타이틀/문구만 다름)

> 모든 앱은 공통적으로 **`gemini_functions.tools`** 를 모델에 전달하고,  
> `enable_automatic_function_calling=True` 로 **자동 도구 호출**을 활성화합니다.

---

## 요구 사항

- Python 3.10+ (권장: 3.11/3.12/3.13)
- 패키지
  ```bash
  pip install google-generativeai python-dotenv streamlit yfinance pytz
  python -m pip install -r ".\chap7\requirements.txt"

  ```

> **Windows 가상환경(venv) 권장**  
> ```powershell
> py -m venv .venv
> .\.venv\Scripts\Activate.ps1
> python -m pip install --upgrade pip
> ```

---

## 환경 변수 (.env)

프로젝트 루트에 `.env` 파일을 만들고 아래 항목을 설정하세요.

```env
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
```

- Streamlit 앱은 `.env` 에서 API 키를 읽고, 없으면 `st.secrets["GOOGLE_API_KEY"]`도 확인합니다.

---

## 실행 방법

### 1) Streamlit – 주가/시간 챗봇 (stock_streamlit.py)

```bash
streamlit run stock_streamlit.py
```

- 페이지 타이틀: “주식 가격을 알려줘~ 🧐”  
- 대화 입력창에 자유롭게 질문하세요.  
  - 예: “AAPL 최근 5일 가격 알려줘”, “뉴욕은 지금 몇 시야?”  
- 모델이 필요 시 `gemini_functions.py`의 도구를 자동 호출해 결과를 답변합니다.

### 2) Streamlit – 시간/일반 챗봇 (what_time_is_it_terminal_streamlit.py)

```bash
streamlit run what_time_is_it_terminal_streamlit.py
```

- 페이지 타이틀: “품격있는 챗봇과 대화하기 🧐”  
- 작동 방식은 1)과 동일하며, 문구/레이아웃만 다릅니다.

### 3) 터미널(콘솔) 챗봇 (what_time_is_it_terminal.py)

```bash
python what_time_is_it_terminal.py
```

- 프롬프트에 입력 → 응답 출력 형식  
- `exit` 입력 시 종료

---

## 주요 코드 포인트

### 도구(Functions) 정의와 등록 – `gemini_functions.py`

- 시간: `pytz.timezone(timezone)` 으로 타임존 처리 후 현재 시간 JSON 문자열 반환
- 주식:
  - `yfinance.Ticker(ticker).info` – 종목 메타 정보
  - `.history(period=...)` – 시세 이력 → `DataFrame.to_markdown()` 변환
  - `.recommendations` – 애널리스트 추천 → `DataFrame.to_markdown()` 변환
- 마지막에 `tools = [ ... ]` 리스트로 함수들을 모델 도구로 등록

### 모델 설정 – Streamlit/터미널 공통

- 모델: `"gemini-2.5-flash"`
- `generation_config` 예시:
  - `temperature`, `top_p`, `top_k`, `max_output_tokens`
- 채팅 세션:
  - `model.start_chat(enable_automatic_function_calling=True)`  
    → 사용자 메시지에 따라 **필요한 도구를 자동 호출**

---

## 예시 프롬프트

- “AAPL 정보 알려줘” → `get_yf_stock_info`
- “AAPL 최근 5일 가격” → `get_yf_stock_history('AAPL', '5d')`
- “AAPL 추천 리포트” → `get_yf_recommendations`
- “뉴욕은 지금 몇 시야?” → `get_current_time('America/New_York')`
- “한국 시간 알려줘” → `get_current_time('Asia/Seoul')`

---

## 트러블슈팅 (특히 Windows + VS Code)

1. **Streamlit 실행 환경이 꼬일 때**
   - VS Code에서 `Ctrl+Shift+P` → **Python: Select Interpreter** → `.venv\Scripts\python.exe` 선택
   - `.vscode/settings.json`의 `python.defaultInterpreterPath`가 Codespaces 경로(`/home/codespace/...`)로 고정돼 있지 않은지 확인

2. **pip가 잘못된 경로를 찾을 때**
   - 터미널을 모두 닫고 다시 열어 venv 재활성화  
   - 그래도 안되면 venv 제거 후 로컬에서 새로 생성:
     ```powershell
     deactivate  # 에러면 무시
     Remove-Item -Recurse -Force .\.venv
     py -m venv .venv
     .\.venv\Scripts\Activate.ps1
     python -m pip install --upgrade pip
     ```

3. **yfinance 응답 지연**
   - 네트워크 이슈일 수 있습니다. 간헐적으로 지연될 수 있으니 재시도하거나 기간을 줄여 요청하세요.

---

## 라이선스

본 예제는 교육/실습 용도로 제공됩니다. API 키/비밀 정보는 반드시 안전하게 관리하세요.
