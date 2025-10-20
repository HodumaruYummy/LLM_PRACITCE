# 📘 품격있는 Gemini 도구 챗봇 (Streamlit/Terminal)

이 저장소는 **Google Gemini**를 사용해 대화 중 자동으로 **함수(도구)** 를 호출하는 챗봇 예제입니다.  
Streamlit 웹 앱과 터미널(콘솔) 앱 두 가지 형태로 제공되며, `yfinance`를 통한 **주가 조회/추천/히스토리/기술지표**와 `pytz`를 활용한 **현재 시간** 조회 도구가 포함되어 있습니다.

---

## 📂 구성 파일

- `gemini_functions.py` : Gemini가 호출하는 **도구 함수 모음**
  - `get_current_time(timezone: str)` – 타임존 기준 현재 시간 JSON 반환
  - `get_yf_stock_info(ticker: str)` – 종목 정보 조회
  - `get_yf_stock_history(ticker: str, period: str)` – 종목 가격 히스토리(markdown)
  - `get_yf_recommendations(ticker: str)` – 애널리스트 추천(markdown)
  - `get_yf_tech_chart(ticker: str, period="6mo", interval="1d", ma_windows=[20,60,120], bb_window=20, bb_std=2.0)` – **이동평균선(20/60/120) + 볼린저밴드(20, 2σ)** 차트(**base64 PNG**)와 최신 값(JSON)을 반환
  - `get_yf_tech_values(ticker: str, period="6mo", interval="1d", ma_windows=[20,60,120], bb_window=20, bb_std=2.0)` – 이동평균선/볼린저밴드 **최신 값만 JSON**으로 반환
  - 마지막에 `tools = [ ... ]` 형태로 위 함수들을 **도구로 등록**

- `stock_streamlit.py` : Streamlit 앱 (챗 UI + 자동 함수 호출)
- `what_time_is_it_terminal.py` : 터미널(콘솔) 챗봇
- `what_time_is_it_terminal_streamlit.py` : Streamlit 앱 (챗 UI + 자동 함수 호출, 타이틀/문구만 다름)

> 모든 앱은 공통적으로 **`gemini_functions.tools`** 를 모델에 전달하고,  
> `enable_automatic_function_calling=True` 로 **자동 도구 호출**을 활성화합니다.

---

## ⚙️ 요구 사항

- Python 3.10+ (권장: 3.11/3.12/3.13)
- 패키지 설치
  ```bash
  pip install google-generativeai python-dotenv streamlit yfinance pytz matplotlib pandas tabulate
  ```

> **Windows 가상환경(venv) 권장**
> ```powershell
> py -m venv .venv
> .\.venv\Scripts\Activate.ps1
> python -m pip install --upgrade pip
> ```

---

## 🔑 환경 변수 (.env)

프로젝트 루트에 `.env` 파일을 만들고 아래 항목을 설정하세요.

```env
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
DART_API_KEY=YOUR_DART_API_KEY
```

- Streamlit 앱은 `.env` 에서 API 키를 읽고, 없으면 `st.secrets["GOOGLE_API_KEY"]`도 확인합니다.

---

## 🚀 실행 방법

### 1) Streamlit – 주가/시간/기술지표 챗봇 (`stock_streamlit.py`)

```bash
streamlit run stock_streamlit.py
```

- 페이지 타이틀: “주식 가격을 알려줘~ 🧐”  
- 대화 입력창에 자유롭게 질문하세요.  
  - 예: “AAPL 최근 5일 가격 알려줘”  
  - 예: “AAPL 이동평균선과 볼린저밴드 차트 보여줘”  
  - 예: “뉴욕은 지금 몇 시야?”  
- 모델이 필요 시 `gemini_functions.py`의 도구를 자동 호출해 결과를 답변합니다.

### 2) Streamlit – 시간/일반 챗봇 (`what_time_is_it_terminal_streamlit.py`)

```bash
streamlit run what_time_is_it_terminal_streamlit.py
```

- 페이지 타이틀: “품격있는 챗봇과 대화하기 🧐”  
- 작동 방식은 1)과 동일하며, 문구/레이아웃만 다릅니다.

### 3) 터미널(콘솔) 챗봇 (`what_time_is_it_terminal.py`)

```bash
python what_time_is_it_terminal.py
```

- 프롬프트 입력 → 응답 출력  
- `exit` 입력 시 종료

---

## 🧰 도구(Functions) 동작 개요

### DART 분기 재무지표
- `get_dart_indicators_quarterly(corp_name: str, years: int=5, fs_div: str="CFS", ticker: Optional[str]=None)`  
  - **DART 공시 기준**으로 최근 N년(기본 5년)의 분기 EPS/ROE/ROA를 표로 반환합니다.  
  - `ticker`를 함께 넘기면 yfinance에서 **분기말 종가**를 가져와 **PER(= 종가 / EPS)** 도 계산해 표에 추가합니다.  
  - 예: `get_dart_indicators_quarterly("현대자동차", years=5, fs_div="CFS", ticker="005380.KS")`

## 🧰 도구(Functions) 동작 개요

### 시간
- `get_current_time(timezone: str)`  
  `pytz.timezone(timezone)` 으로 타임존을 해석하고, 현재 시간을 `{"timezone": "...","current_time": "YYYY-MM-DD HH:MM:SS"}` 형태의 JSON 문자열로 반환합니다.

### 주식
- `get_yf_stock_info(ticker: str)`  
  `yfinance.Ticker(ticker).info` 를 그대로 반환합니다(문자열).

- `get_yf_stock_history(ticker: str, period: str)`  
  `yfinance.Ticker(ticker).history(period=...)` → `DataFrame.to_markdown()` 으로 변환해 반환합니다.

- `get_yf_recommendations(ticker: str)`  
  `yfinance.Ticker(ticker).recommendations` → `DataFrame.to_markdown()` 으로 변환해 반환합니다.

- `get_yf_tech_chart(...)`  
  `yf.download()`로 시세를 받고,  
  - 단순이동평균(SMA): `Close.rolling(w).mean()` (기본 20/60/120)
  - 볼린저밴드: `mid = MA(window=20)`, `upper/lower = mid ± 2 * std(window=20)`  
  하나의 차트로 그려 **PNG(base64)** 와 최신 지표 값(JSON)을 함께 반환합니다.
  
  **프론트에서 base64 이미지 렌더링 예시**
  ```python
  # Python/Streamlit 등에서
  payload = json.loads(get_yf_tech_chart("AAPL"))
  img_b64 = payload["image_base64"]
  img_src = f"data:image/png;base64,{img_b64}"
  # Streamlit
  # st.image(img_src)  # 또는 st.image(base64.b64decode(img_b64))
  ```

- `get_yf_tech_values(...)`  
  차트는 그리지 않고 **최신 수치만** JSON으로 반환합니다.

> 롤링 윈도 크기 초반에는 NaN이 발생할 수 있으므로, 최신 값 계산 시 None 처리되어 반환됩니다.

---

## 💬 예시 프롬프트

- “현대자동차 5년간 분기 EPS” → `get_dart_indicators_quarterly("현대자동차", years=5)`
- “현대자동차 5년 분기 EPS와 PER” → `get_dart_indicators_quarterly("현대자동차", years=5, ticker="005380.KS")`

## 💬 예시 프롬프트

- “AAPL 정보 알려줘” → `get_yf_stock_info("AAPL")`
- “AAPL 최근 5일 가격” → `get_yf_stock_history("AAPL", "5d")`
- “AAPL 추천 리포트” → `get_yf_recommendations("AAPL")`
- “뉴욕은 지금 몇 시야?” → `get_current_time("America/New_York")`
- “한국 시간 알려줘” → `get_current_time("Asia/Seoul")`
- “AAPL 이동평균선과 볼린저밴드 차트” → `get_yf_tech_chart("AAPL")`
- “AAPL 기술지표 수치만 알려줘” → `get_yf_tech_values("AAPL")`

---

## 🛠 트러블슈팅 (특히 Windows + VS Code)

1. **Streamlit 실행 환경 꼬임**
   - VS Code에서 `Ctrl+Shift+P` → **Python: Select Interpreter** → `.venv\Scripts\python.exe` 선택
   - `.vscode/settings.json`의 `python.defaultInterpreterPath` 확인 (Codespaces 경로로 고정되어 있지 않은지)

2. **pip 경로 오류**
   - 터미널을 닫고 venv 재활성화  
   - 필요 시 venv 재생성:
     ```powershell
     deactivate  # 에러면 무시
     Remove-Item -Recurse -Force .\.venv
     py -m venv .venv
     .\.venv\Scripts\Activate.ps1
     python -m pip install --upgrade pip
     ```

3. **yfinance 응답 지연**
   - 네트워크 환경 문제일 수 있음 → 요청 기간을 짧게 하거나 재시도

---

## 📜 라이선스

본 예제는 교육/실습 용도로 제공됩니다.  
API 키/비밀 정보는 반드시 안전하게 관리하세요.
