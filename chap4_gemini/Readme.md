README
개요

이 프로젝트는 PDF → TXT 전처리(헤더/푸터 제외) 후, Upstage Solar Chat Completions API로 요약을 생성하는 파이프라인입니다. 긴 문서는 청킹(Chunking) 으로 부분 요약 후 최종 요약을 생성할 수 있습니다.

주요 파일
chap3/
 ├─ pdf_summary.py                  # PDF→TXT→요약 (Solar API)
 ├─ LectureOT(2025-2).pdf          # 입력 PDF (예시)
 └─ output/
     ├─ LectureOT(2025-2)_with_preprocessing.txt
     └─ LEEYS_SUMMARY.txt          # 최종 요약 결과

요구 사항

Python 3.9+

가상환경(권장)

패키지

openai==1.52.2

pymupdf

python-dotenv

(옵션) google-generativeai (Gemini 실습 시)

설치
# Windows PowerShell 예시
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install openai==1.52.2 pymupdf python-dotenv
# (옵션) Gemini도 사용할 경우
pip install google-generativeai

환경 변수(.env)

프로젝트 루트에 .env 파일 생성 후 아래 키를 추가하세요.

Solar_api_key=YOUR_UPSTAGE_SOLAR_API_KEY
# (옵션) Gemini 사용 시
GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY

사용법
1) 기본: PDF 요약 실행

chap3/pdf_summary.py 를 실행하면,

output/{원본파일명}_with_preprocessing.txt (전처리 결과)

output/LEEYS_SUMMARY.txt (최종 요약)
이 생성됩니다.

# 프로젝트 루트에서
python .\chap3\pdf_summary.py

2) PDF → TXT 전처리만 사용

pdf_to_text() 함수가 헤더/푸터 영역(기본 80px) 을 제외한 텍스트를 추출해 output/…_with_preprocessing.txt 로 저장합니다. 다른 스크립트에서 재활용 가능합니다.

3) (옵션) 청킹 요약 버전

긴 본문에서 잘림을 피하려면 summarize_txt() 내부에 청킹 로직을 활성화하세요(이미 제공된 청킹 버전 예시 참고).

청킹 크기 예시: CHUNK_CHAR_LIMIT = 4000

부분 요약 max_tokens ≈ 700~900, 최종 요약 max_tokens ≈ 1000~1400 권장

파라미터 설명
헤더/푸터 제거 높이
header_height = 80
footer_height = 80


값 ↑: 상/하단 더 많이 제거 → 본문 줄어듦

값 ↓: 본문 포함 범위 ↑

PDF 레이아웃에 따라 적절히 조절하거나, 페이지 높이 비율(rect.height * 0.1)로도 설정 가능

토큰/길이 관련 팁

요약이 잘리면 max_tokens를 늘리거나, 청킹을 적용하세요.

프롬프트는 간결할수록 토큰 절약에 유리합니다.

자주 발생하는 오류 & 해결

ModuleNotFoundError: No module named 'pymupdf'
→ pip install pymupdf 실행, 현재 활성 가상환경에 설치됐는지 확인

AttributeError: module 'ntpath' has no attribute 'basenmae'
→ 오타입니다. os.path.basename으로 수정

NameError: name 'text' is not defined
→ 추출 변수명 확인(text, header, footer). 전처리 루프 내 변수 일치 필요

IndentationError: unindent does not match any outer indentation level
→ 탭/스페이스 혼용 방지. 에디터에서 공백(스페이스)만 사용 권장

요약이 빈 응답/잘림
→ max_tokens 상향 + 청킹 적용. (부분/최종 요약 분리)