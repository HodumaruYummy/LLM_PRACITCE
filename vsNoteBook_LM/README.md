# LLM_PRACITCE
# PDF → Gemini 요약기 (Codespaces Ready)

PyMuPDF로 PDF에서 본문 텍스트를 추출하고, Google Gemini API로 요약을 생성합니다.  
**GitHub Codespaces**와 **로컬** 모두에서 쉽게 돌아가도록 구성했습니다.

---

## 1. 요구 사항

- Python 3.10+ (Codespaces 기본 이미지는 3.11 사용)
- Google Generative AI API 키 (`GOOGLE_API_KEY`)

---

## 2. 빠른 시작 (GitHub Codespaces 권장)

# 의존성 설치
pip install -r requirements.txt

# 1) --pdf 생략 → 폴더 최신 PDF 자동 선택
python pdf_to_text_summary_gemini.py

# 2) 특정 파일 지정 (공백 있으면 따옴표)
python pdf_to_text_summary_gemini.py --pdf "초등학생을 위한 라즈베리파이.pdf"

# 3) 자원 이슈가 있으면 더 보수적으로
python pdf_to_text_summary_gemini.py --chunk-size 3000 --max-chunks 40 --sleep 0.5

-->cd /workspaces/LLM_PRACITCE/vsNoteBook_LM 경로를 잘 찾아줘야함.


git clone <your-repo-url>
cd your-repo
python -m venv .venv
source .venv/bin/activate   # (Windows) .venv\Scripts\activate
pip install -r requirements.txt

cp .env
# .env 열어서 GOOGLE_API_KEY 입력

python app.py --pdf ./sample.pdf


git add .
git commit -m "feat: pdf→text→gemini summarize pipeline for Codespaces"
git push origin main

