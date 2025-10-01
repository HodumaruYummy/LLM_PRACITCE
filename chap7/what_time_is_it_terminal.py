import google.generativeai as genai
import os
from dotenv import load_dotenv
import json

# gemini_tools.py 파일에서 함수와 도구 목록을 가져옵니다.
from gemini_functions import tools

# --- 환경 설정 ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY 환경 변수를 설정해주세요.")
genai.configure(api_key=api_key)


# --- 모델 및 채팅 설정 ---
# 모델을 설정할 때, import해온 tools를 전달합니다.
model = genai.GenerativeModel(
        model_name="gemini-2.5-flash", 
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=2048,
        ),
    tools=tools, system_instruction="고상하고 기품있게 이야기해줘. 그리고 다양한 이모지를 써줘"
)

# 자동 함수 호출을 활성화하여 채팅 세션을 시작합니다.
chat = model.start_chat(enable_automatic_function_calling=True)

print("Gemini 챗봇 시작! (종료하려면 'exit' 입력)")
print("=" * 30)

# --- 메인 실행 루프 ---
while True:
    try:
        user_input = input("사용자\t: ")
        if user_input.lower() == "exit":
            print("챗봇을 종료합니다.")
            break

        # 사용자의 메시지를 전송하면, 모델이 알아서 gemini_tools의 함수를 실행하고 답변합니다.
        response = chat.send_message(user_input)
        
        print(f"AI\t: {response.text}")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
        break