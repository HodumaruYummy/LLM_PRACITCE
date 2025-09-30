# 파일명: create_quiz_book_gemini.py
import google.generativeai as genai
import os
import glob
from dotenv import load_dotenv
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
def main():
    """이미지 폴더를 순회하며 퀴즈 문제집을 생성하고, 올바른 이미지 경로를 지정합니다."""
    try:
        model = setup_gemini()

        # --- 경로 설정 ---
        # 퀴즈를 만들 이미지가 있는 폴더
        image_folder = r'C:\Users\ziclp\OneDrive\Desktop\LLM Assignment\1week\PRACTICE1\chap6\pics'
        # 완성된 문제집이 저장될 파일
        output_file_path = r'C:\Users\ziclp\OneDrive\Desktop\LLM Assignment\1week\PRACTICE1\chap6\output\image_quiz_book_gemini.md'
        # ----------------

        supported_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
        all_files = glob.glob(os.path.join(image_folder, '*'))
        image_paths = [f for f in all_files if f.lower().endswith(supported_extensions)]

        quiz_book_content = '# 🖼️ 이미지 퀴즈 문제집 (Gemini)\n\n'
        question_number = 1

        if not image_paths:
            print(f"경고: '{image_folder}' 경로에서 이미지를 찾을 수 없습니다.")
            return

        total_images = len(image_paths)
        print(f"총 {total_images}개의 이미지로 문제집 생성을 시작합니다.")

        # 마크다운 파일이 저장될 폴더의 경로를 가져옵니다.
        output_dir = os.path.dirname(output_file_path)

        for image_path in image_paths:
            try:
                print(f"({question_number}/{total_images}) '{os.path.basename(image_path)}' 문제 생성 중...")
                quiz = generate_image_quiz(model, image_path)

                # --- ⭐️ 수정된 부분: 올바른 상대 경로 생성 ---
                # output 폴더에서 이미지 파일까지의 상대 경로를 계산합니다.
                relative_image_path = os.path.relpath(image_path, output_dir)
                # 마크다운에서는 역슬래시(\) 대신 슬래시(/)를 사용하므로 변경해줍니다.
                markdown_image_path = relative_image_path.replace('\\', '/')
                # -------------------------------------------

                # 마크다운 형식으로 내용 추가
                quiz_book_content += f'## 문제 {question_number}\n\n'
                # 생성된 상대 경로를 이미지 태그에 적용합니다.
                quiz_book_content += f'![image]({markdown_image_path})\n\n'
                quiz_book_content += quiz + '\n\n---\n\n'

                question_number += 1
            except Exception as e:
                print(f"  -> 오류: '{image_path}' 처리 중 문제가 발생했습니다: {e}")
                continue

        # output 폴더가 없으면 생성
        os.makedirs(output_dir, exist_ok=True)

        # 최종 결과물을 마크다운 파일로 저장
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(quiz_book_content)

        print(f"\n✅ 성공! 문제집이 '{output_file_path}' 파일로 저장되었습니다.")

    except Exception as e:
        print(f"프로세스 실행 중 심각한 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()