# 파일명: create_quiz_book_gemini.py
import google.generativeai as genai
import os
import glob
from dotenv import load_dotenv
import json
from PIL import Image # 이미지의 MIME 타입을 정확히 파악하기 위해 Pillow 라이브러리 사용

# --- 환경 설정 및 모델 초기화 ---
def setup_gemini():
    """API 키를 로드하고 Gemini 모델을 설정합니다."""
    # 로컬 환경(.env)에서 API 키 로드
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

    
    if not api_key:
        raise ValueError("API 키를 찾을 수 없습니다.")
    
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 4096,
        }
    )
    return model

# --- 이미지 데이터 준비 ---
def get_image_data(image_path):
    """이미지 파일에서 바이트 데이터와 MIME 타입을 추출합니다."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"'{image_path}' 파일을 찾을 수 없습니다.")
    
    img = Image.open(image_path)
    # Pillow 라이브러리를 통해 파일 확장자와 무관하게 실제 이미지 포맷을 감지
    mime_type = f"image/{img.format.lower()}"
    
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
        
    return {'mime_type': mime_type, 'data': image_bytes}

# --- 이미지 기반 퀴즈 생성 ---
def generate_image_quiz(model, image_path):
    """주어진 이미지로 하나의 퀴즈를 생성합니다."""
    image_data = get_image_data(image_path)
    
    prompt = """
    제공된 이미지를 바탕으로, 다음과 같은 양식으로 퀴즈를 만들어주세요. 
    정답은 1~4 중 하나만 해당하도록 출제하세요.
    토익 리스닝 문제 스타일로 문제를 만들어주세요.
    
    ----- 예시 -----
    Q: 다음 이미지에 대한 설명 중 옳지 않은 것은 무엇인가요?
    - (1) 베이커리에서 사람들이 빵을 사고 있는 모습이 담겨 있습니다.
    - (2) 맨 앞에 서 있는 사람은 빨간색 셔츠를 입고 있습니다.
    - (3) 기차를 타기 위해 줄을 서 있는 사람들이 있습니다.
    - (4) 점원은 노란색 티셔츠를 입고 있습니다.

    Listening: Which of the following descriptions of the image is incorrect?
    - (1) It shows people buying bread at a bakery.
    - (2) The person standing at the front is wearing a red shirt.
    - (3) There are people lining up to take a train.
    - (4) The clerk is wearing a yellow T-shirt.
        
    정답: (4) 점원은 노란색 티셔츠가 아닌 파란색 티셔츠를 입고 있습니다.
    (주의: 정답은 1~4 중 하나만 선택되도록 출제하세요.)
    ======
    """
    
    response = model.generate_content([prompt, image_data])
    return response.text

# --- 메인 실행 함수 ---
# --- 메인 실행 함수 ---
def main():
    """이미지 폴더를 순회하며 마크다운과 JSON 문제집을 생성합니다."""
    try:
        model = setup_gemini()

        # --- 경로 설정 ---
        image_folder = r'C:\Users\ziclp\OneDrive\Desktop\LLM Assignment\1week\PRACTICE1\chap6\pics'
        output_folder = r'C:\Users\ziclp\OneDrive\Desktop\LLM Assignment\1week\PRACTICE1\chap6\output'
        
        md_output_path = os.path.join(output_folder, 'image_quiz_book_gemini.md')
        # ⭐️ 요청하신 JSON 파일 경로
        json_output_path = os.path.join(output_folder, 'image_quiz_eng.json')
        # ----------------

        supported_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
        all_files = glob.glob(os.path.join(image_folder, '*'))
        image_paths = [f for f in all_files if f.lower().endswith(supported_extensions)]

        quiz_book_content = '# 🖼️ 이미지 퀴즈 문제집 (Gemini)\n\n'
        eng_dict = []  # ⭐️ 영어 퀴즈를 저장할 리스트 (요청하신 변수명 사용)
        question_number = 1

        if not image_paths:
            print(f"경고: '{image_folder}' 경로에서 이미지를 찾을 수 없습니다.")
            return

        total_images = len(image_paths)
        print(f"총 {total_images}개의 이미지로 문제집 생성을 시작합니다.")

        for image_path in image_paths:
            try:
                filename = os.path.basename(image_path)
                print(f"({question_number}/{total_images}) '{filename}' 문제 생성 중...")
                
                # 변수 q 대신 full_quiz를 사용
                full_quiz = generate_image_quiz(model, image_path)

                # --- ⭐️ 요청하신 영어 문제 추출 및 저장 로직 ---
                try:
                    # 'Listening: '와 '정답:' 사이의 텍스트를 추출합니다.
                    eng = full_quiz.split('Listening: ')[1].split('정답:')[0].strip()

                    # 딕셔너리 형태로 만들어 리스트에 추가합니다.
                    eng_dict.append({
                        'no': question_number,
                        'eng': eng,
                        'img': filename
                    })
                except IndexError:
                    # 만약 모델 출력이 예상과 달라 split에 실패할 경우를 대비
                    print(f"  -> 경고: '{filename}'에서 영어 문제 부분을 추출하지 못했습니다.")
                # -------------------------------------------

                # --- 마크다운 파일 내용 생성 ---
                relative_image_path = os.path.relpath(image_path, output_folder)
                markdown_image_path = relative_image_path.replace('\\', '/')
                
                quiz_book_content += f'## 문제 {question_number}\n\n'
                quiz_book_content += f'![image]({markdown_image_path})\n\n'
                quiz_book_content += full_quiz + '\n\n---\n\n'
                # ---------------------------
                
                question_number += 1
            except Exception as e:
                print(f"  -> 오류: '{image_path}' 처리 중 문제가 발생했습니다: {e}")
                continue

        # --- 파일 저장 ---
        os.makedirs(output_folder, exist_ok=True)

        # 1. 마크다운 파일 저장
        with open(md_output_path, 'w', encoding='utf-8') as f:
            f.write(quiz_book_content)
        print(f"\n✅ 성공! 마크다운 문제집이 '{md_output_path}' 파일로 저장되었습니다.")

        # 2. ⭐️ JSON 파일 저장 (요청하신 코드 적용)
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(eng_dict, f, ensure_ascii=False, indent=4)
        print(f"✅ 성공! 영어 퀴즈 JSON 파일이 '{json_output_path}' 파일로 저장되었습니다.")
        # -----------------

    except Exception as e:
        print(f"프로세스 실행 중 심각한 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()