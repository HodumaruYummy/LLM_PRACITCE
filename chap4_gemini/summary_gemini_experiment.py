import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY가 .env 파일에 설정되지 않았습니다.")
genai.configure(api_key=api_key)

def summarize_txt_gemini(file_path: str):
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        txt = f.read()

    prompt = f'''
    너는 다음 글을 요약하는 봇이다. 아래 글을 읽고 , 저자의 문제 인식과 주장을 파악하고, 주요 내용을 요약해라. 작성해야하는 포맷은 다음과 같다.

    # 제목
    ## 저자의 문제 인식 및 주장 (15문장 이내)
    ## 저자 소개

    ==============================이하 텍스트 ============================
    {txt}
    '''
    
    # API 호출
    response = model.generate_content(prompt)

    # --- (수정된 부분) ---
    # 1. 편리한 단축 경로 (기존 방식)
    summary_shortcut = response.text

    # 2. OpenAI/Upstage와 유사하게 전체 경로로 직접 접근 (새로운 방식)
    #    response.choices[0].message.content 와 유사한 구조입니다.
    #    - Gemini의 `candidates`는 OpenAI의 `choices`에 해당합니다.
    #    - Gemini의 `content`는 OpenAI의 `message`에 해당합니다.
    #    - Gemini의 `parts[0].text`는 OpenAI의 `content`에 해당합니다.
    try:
        summary_full_path = response.candidates[0].content.parts[0].text
    except (IndexError, AttributeError) as e:
        print(f"오류: 응답 구조에서 텍스트를 찾을 수 없습니다. API 응답을 확인해주세요. Error: {e}")
        # 응답에 콘텐츠가 없는 경우를 대비하여 예외 처리
        summary_full_path = "요약 생성에 실패했습니다."


    print("\n--- 단축 경로(.text) 결과 ---")
    print(summary_shortcut)
    
    print("\n--- 전체 경로(.candidates[0]...) 결과 ---")
    print(summary_full_path)
    
    # 두 결과는 동일하므로, 어떤 것을 사용해도 괜찮습니다.
    # 보통은 편리한 .text를 사용합니다.
    return summary_full_path # 또는 summary_shortcut

if __name__ == '__main__':
    file_path = 'output/대전사회복지사협회-_위기대응_매뉴얼_통합본_개정판_with_preprocessing.txt'
    
    if os.path.exists(file_path):
        summary = summarize_txt_gemini(file_path)
        
        output_filename = 'output/대전사회복지사협회-_위기대응_매뉴얼_통합본_개정판_summary_gemini.txt'
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        print(f"\n✅ Gemini 요약이 '{output_filename}' 파일에 저장되었습니다.")
    else:
        print(f"오류: '{file_path}' 파일을 찾을 수 없습니다.")