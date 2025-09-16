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

1) 이 레포를 GitHub에 푸시합니다.

2) GitHub에서 **Code ▶ Create codespace on main** 클릭.

3) (선택 1) Codespaces에 `.env` 파일 만들기  
   - `.env.example`를 복사해 `.env`로 이름 변경 후 키 입력
   ```bash
   cp .env.example .env
   # .env 열어서 GOOGLE_API_KEY 값 설정
echo "export GOOGLE_API_KEY=YOUR_KEY" >> ~/.bashrc
source ~/.bashrc

(선택 2) Codespaces 시크릿 사용 (보안 권장)

Codespaces 터미널에서 다음으로 영구 등록:

echo "export GOOGLE_API_KEY=YOUR_KEY" >> ~/.bashrc
source ~/.bashrc

의존성 설치(자동). 자동이 안 됐다면:

pip install -r requirements.txt

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

