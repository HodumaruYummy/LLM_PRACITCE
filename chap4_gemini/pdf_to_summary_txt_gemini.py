import google.generativeai as genai
from dotenv import load_dotenv
import os
import fitz  # PyMuPDF
from datetime import datetime

# ✅ 1. .env에서 API 키 불러오기
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY가 .env 파일에 설정되지 않았습니다.")
genai.configure(api_key=api_key)

# ✅ 2. PDF를 텍스트로 추출하는 함수
def pdf_to_text(pdf_file_path: str) -> str:
    doc = fitz.open(pdf_file_path)  # PDF 열기
    header_height = 80
    footer_height = 80
    full_text = ''

    for page in doc:
        rect = page.rect
        # 상하단 여백 제거
        text = page.get_text(clip=(0, header_height, rect.width, rect.height - footer_height))
        full_text += text + '\n' + '-'*50 + '\n'

    # 추출된 텍스트 저장
    pdf_file_name = os.path.splitext(os.path.basename(pdf_file_path))[0]
    os.makedirs('output', exist_ok=True)
    txt_file_path = f'output/{pdf_file_name}_with_preprocessing.txt'
    with open(txt_file_path, 'w', encoding='utf-8') as f:
        f.write(full_text)
    
    return txt_file_path

# ✅ 3. Gemini를 통해 요약하는 함수
def summarize_txt_gemini(file_path: str) -> str:
    model = genai.GenerativeModel('gemini-2.5-pro')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        txt = f.read()

    prompt = f'''
    너는 다음 글을 요약하는 봇이다. 아래 글을 읽고, 저자의 문제 인식과 주장을 파악하고, 주요 내용을 요약해라.
    작성해야 하는 포맷은 다음과 같다:

    # 제목
    ## 저자의 문제 인식 및 주장 (15문장 이내)
    ## 저자 소개

    ==============================이하 텍스트 ============================
    {txt}
    '''
    
    # API 호출
    response = model.generate_content(prompt)

    try:
        summary = response.candidates[0].content.parts[0].text
    except (IndexError, AttributeError) as e:
        print(f"❌ 오류: 응답에서 텍스트를 찾을 수 없습니다. Error: {e}")
        summary = "요약 생성에 실패했습니다."

    return summary

# ✅ 4. 전체 흐름을 실행하는 함수
def summarize_pdf(pdf_file_path: str):
    print(f"[1] PDF 파일 → 텍스트 변환 중: {pdf_file_path}")
    txt_file_path = pdf_to_text(pdf_file_path)
    print(f"   ✅ 텍스트 저장: {txt_file_path}")

    print(f"[2] 텍스트 요약 중...")
    summary = summarize_txt_gemini(txt_file_path)
    print(f"   ✅ 요약 완료")

    # 결과 저장
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file_path = f'output/summary_{now}.txt'
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(summary)

    print(f"[3] 요약 결과 저장 완료: {output_file_path}")

# ✅ 5. 메인 실행
if __name__ == '__main__':
    pdf_file_path = '블루멤버스_개인회원_가이드북.pdf'
    
    if os.path.exists(pdf_file_path):
        summarize_pdf(pdf_file_path)
    else:
        print(f"❌ 오류: '{pdf_file_path}' 파일이 존재하지 않습니다.")
