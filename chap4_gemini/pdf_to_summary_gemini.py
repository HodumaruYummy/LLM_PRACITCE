import google.generativeai as genai
from dotenv import load_dotenv
import os
import pymupdf

load_dotenv()
# (수정) .env 파일에서 GOOGLE_API_KEY를 불러옵니다.
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY가 .env 파일에 설정되지 않았습니다.")
genai.configure(api_key=api_key)

# 이 함수는 API와 무관하므로 수정할 필요가 없습니다.
def pdf_to_text(pdf_file_path:str):
    doc = pymupdf.open(pdf_file_path)
    # ... (기존 코드와 동일) ...
    header_height = 80
    footer_height = 80
    full_text = ''
    for page in doc:
        rect = page.rect
        text = page.get_text(clip=(0, header_height, rect.width, rect.height-footer_height))
        full_text += text + '\n---------------------------------------------------\n'

    pdf_file_name = os.path.splitext(os.path.basename(pdf_file_path))[0]
    os.makedirs('output', exist_ok=True)
    txt_file_path = f'output/{pdf_file_name}_with_preprocessing.txt'
    with open(txt_file_path, 'w', encoding='utf-8') as f:
        f.write(full_text)
    return txt_file_path

# (수정) summarize_txt 함수를 Gemini API 용으로 변경
def summarize_txt_gemini(file_path:str):
    safety_settings = {
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    }
    model = genai.GenerativeModel(
        'gemini-2.5-pro', # 유효한 모델 이름
        safety_settings=safety_settings,
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 1024,
        }
    )
    with open(file_path, 'r', encoding='utf-8') as f:
        txt = f.read()

    prompt = f'''
    너는 다음 글을 요약하는 봇이다. 아래 글을 읽고 , 저자의 문제 인식과 주장을 파악하고, 주요 내용을 요약해라. 작성해야하는 포맷은 다음과 같다.

    # 제목
    ## 저자의 문제 인식 및 주장 (50문장 이내)
    ## 저자 소개

    ==============================이하 텍스트 ============================
    {txt}
    '''
    response = model.generate_content(prompt)

    if not response.parts:
        print("오류: API로부터 콘텐츠를 받지 못했습니다.")
        print(f"응답 종료 이유: {response.candidates[0].finish_reason}")
        return "요약 생성에 실패했습니다."
        
    return response.text

def summarize_pdf(pdf_file_path: str, output_file_path:str):
    print(f"1. '{pdf_file_path}'에서 텍스트 추출을 시작합니다...")
    txt_file_path = pdf_to_text(pdf_file_path)
    print(f"   -> 텍스트 추출 완료: '{txt_file_path}'")
    
    print(f"2. '{txt_file_path}' 파일의 요약을 시작합니다...")
    # (수정) Gemini 요약 함수를 호출
    summary = summarize_txt_gemini(txt_file_path)
    print("   -> 요약 완료.")

    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    print(f"3. 최종 요약본이 '{output_file_path}'에 저장되었습니다.")


if __name__ == '__main__':
    pdf_file_path = '대전사회복지사협회-_위기대응_매뉴얼_통합본_개정판.pdf'
    output_file_path = 'output/대전사회복지사협회-_위기대응_매뉴얼_통합본_개정판_SUMMARY_GEMINI.txt'
    
    summarize_pdf(pdf_file_path, output_file_path)