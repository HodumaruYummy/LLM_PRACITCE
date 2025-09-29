# 📦 Python Requests 라이브러리

## 🔎 개요
[`requests`](https://docs.python-requests.org/en/latest/)는 파이썬에서 **HTTP 요청(REST API 호출)** 을 간단하고 직관적으로 보낼 수 있게 해주는 라이브러리입니다.  
웹 서비스와 데이터를 주고받거나 API와 상호작용할 때 가장 널리 사용됩니다.

---

## ⚡ 주요 역할
- GET, POST, PUT, DELETE 등 **HTTP 요청 메서드** 제공
- **쿼리 파라미터**, **헤더**, **쿠키**, **인증 정보** 등을 쉽게 설정
- **JSON, 파일, 폼 데이터 전송** 지원
- 응답(Response)을 **텍스트, JSON, 바이트** 등 다양한 형태로 변환 가능
- **세션(Session)** 지원 → 쿠키/헤더/연결 재사용으로 성능 향상
- **예외 처리 및 타임아웃** 설정 지원
- **파일 업로드/다운로드** 편리하게 지원

---

## 🛠️ 기본 사용법

### 1. 설치
```bash
pip install requests
```

### 2. GET 요청
```python
import requests

r = requests.get("https://httpbin.org/get", params={"q": "hello"})
print(r.status_code)   # HTTP 상태 코드
print(r.json())        # JSON 응답을 dict로 변환
```

### 3. POST 요청
```python
# JSON 전송
r = requests.post("https://httpbin.org/post", json={"name": "Alice"})

# 폼 데이터 전송
r = requests.post("https://httpbin.org/post", data={"id": "kim", "pw": "1234"})
```

### 4. 헤더, 쿠키, 타임아웃
```python
r = requests.get(
    "https://example.com",
    headers={"User-Agent": "MyApp/1.0"},
    cookies={"sessionid": "abc123"},
    timeout=10
)
```

### 5. 파일 업로드
```python
files = {"file": ("report.png", open("report.png", "rb"), "image/png")}
r = requests.post("https://httpbin.org/post", files=files)
```

### 6. 파일 다운로드
```python
with requests.get("https://example.com/large.zip", stream=True) as r:
    with open("large.zip", "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
```

### 7. 세션 사용
```python
with requests.Session() as s:
    s.headers.update({"Authorization": "Bearer <TOKEN>"})
    r1 = s.get("https://api.example.com/me")
    r2 = s.post("https://api.example.com/items", json={"name": "banana"})
```

---

## 📑 Response 객체 주요 속성
- `status_code` → HTTP 상태 코드 (200, 404 등)
- `headers` → 응답 헤더
- `text` → 디코딩된 문자열 응답
- `content` → 원본 바이트 데이터
- `json()` → JSON 응답을 dict로 변환

---

## ⚠️ 주의할 점
- `import request` (❌) → `import requests` (✅)  
- 대용량 파일은 반드시 `stream=True`로 받아야 메모리 문제를 피할 수 있음  
- `timeout`과 `raise_for_status()`를 꼭 활용해 네트워크 장애에 대비할 것  

---

## 📚 참고 자료
- [공식 문서](https://docs.python-requests.org/en/latest/)
- [HTTP 상태 코드 위키](https://developer.mozilla.org/ko/docs/Web/HTTP/Status)
