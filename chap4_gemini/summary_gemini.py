import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
# (수정) .env 파일에서 GOOGLE_API_KEY를 불러옵니다.
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY가 .env 파일에 설정되지 않았습니다.")
genai.configure(api_key=api_key)

def summarize_txt_gemini(file_path: str):
    # (수정) Gemini 모델 및 generation_config 설정
    model = genai.GenerativeModel(
        'gemini-2.5-flash',
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 2048,
        }
    )
    
    with open(file_path, 'r', encoding='utf-8') as f:
        txt = f.read()

    # (수정) Gemini에 맞는 프롬프트 형식
    prompt = f'''
    너는 다음 글을 요약하는 봇이다. 아래 글을 읽고 , 저자의 문제 인식과 주장을 파악하고, 주요 내용을 요약해라. 작성해야하는 포맷은 다음과 같다.

    # 제목
    ## 저자의 문제 인식 및 주장 (15문장 이내)
    ## 저자 소개

    ==============================이하 텍스트 ============================

    {txt}
    '''

    #print(prompt)
    print('================================================================')

    # (수정) Gemini API 호출
    response = model.generate_content(prompt)

    return response.text

if __name__ == '__main__':
    file_path = 'output/KCI_FI003037864.txt'

    summary = summarize_txt_gemini(file_path)
    
    # (수정) Gemini로 생성된 요약 파일을 저장
    output_filename = 'output/KCI_FI003037864_summary_gemini.txt'
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    print(f"\n✅ Gemini 요약이 '{output_filename}' 파일에 저장되었습니다.")