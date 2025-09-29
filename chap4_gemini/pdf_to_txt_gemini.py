# PDF 파일을 처리하기 위한 PyMuPDF 라이브러리를 import합니다.
import pymupdf
# 파일 경로 및 이름과 같은 운영 체제 관련 작업을 위한 os 라이브러리를 import합니다.
import os
# (추가) Gemini API 사용을 위한 라이브러리를 import합니다.
import google.generativeai as genai
# (추가) .env 파일에서 환경 변수를 불러오기 위한 라이브러리입니다.
from dotenv import load_dotenv

# --- (추가) Gemini API 키 설정 ---
load_dotenv() # .env 파일 로드
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("환경 변수 'GOOGLE_API_KEY'를 설정해주세요. (.env 파일 확인)")
genai.configure(api_key=GOOGLE_API_KEY)
# --------------------------------

# 텍스트를 추출할 PDF 파일의 경로를 지정합니다.
pdf_file_path = "KCI_FI003037864.pdf"
# 지정된 PDF 파일을 엽니다.
doc = pymupdf.open(pdf_file_path)

# PDF의 모든 페이지에서 추출된 텍스트를 저장하기 위해 빈 문자열을 초기화합니다.
full_text = ''

# 문서의 모든 페이지를 하나씩 반복합니다.
for page in doc:
    # 현재 페이지에서 텍스트를 추출합니다.
    text = page.get_text()
    # 추출된 텍스트를 'full_text' 변수에 추가합니다.
    full_text += text



# 원본 PDF 파일 경로에서 파일 이름만 추출합니다 (예: "LectureOT(2025-2).pdf").
pdf_file_name_with_ext = os.path.basename(pdf_file_path)
# 파일 이름에서 확장자(.pdf)를 제거하여 기본 이름만 얻습니다 (예: "LectureOT(2025-2)").
pdf_file_name = os.path.splitext(pdf_file_name_with_ext)[0]

# (수정) 'output' 폴더가 없으면 생성합니다.
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# 추출된 텍스트를 저장할 출력 .txt 파일의 경로를 만듭니다 (예: "output/LectureOT(2025-2).txt").
txt_file_path = f"{output_dir}/{pdf_file_name}.txt"
# 쓰기 모드('w')와 UTF-8 인코딩으로 출력 파일을 엽니다.
# 'with' 문은 파일 작업이 완료되면 파일이 자동으로 닫히도록 보장합니다.
with open(txt_file_path, 'w', encoding='utf-8') as f:
    # 수집된 모든 텍스트를 .txt 파일에 씁니다.
    f.write(full_text)