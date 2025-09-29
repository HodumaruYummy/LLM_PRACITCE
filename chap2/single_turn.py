from openai import OpenAI # openai==1.52.2
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("Solar_api_key")
 
client = OpenAI(
    api_key=api_key,
    base_url="https://api.upstage.ai/v1"
)

while True:
    user_input = input("User: ")
    if user_input.lower() in ['exit', 'quit']:
        print("Exiting the chat.")
        break

    stream = client.chat.completions.create(
        model="solar-pro2",
        temperature=0.7,
        max_tokens=256,
        messages=[
            {
                "role": "system",
                "content": "너는 내 친구야!"
            },
            {
                "role": "user",
                "content": user_input
            }
        ],
        stream=True,
    )
    print("AI: ", end="", flush=True)

    # ✅ 스트리밍 토큰만 이어 붙여 출력
    for chunk in stream:
        #한 번에 전체 응답이 오는 게 아니라 조각(chunk) 단위
        #for chunk in stream:으로 토큰 조각들을 하나씩 받아옴
        delta = getattr(chunk.choices[0].delta, "content", None) # delta가 없을 수도 있으니 안전하게 가져오기
        #getattr(obj, "속성명", 기본값) 은 객체에 속성이 있으면 값을 가져오고, 없으면 기본값을 돌려주는 함수
        # delta = chunk.choices[0].delta.get("content", None) # delta가 없을 수도 있으니 안전하게 가져오기
        #chunk.choices[0].delta 스트리밍 모드에서는 전체 메시지가 한 번에 오지 않고, "delta" 라는 객체에 “추가된 부분”만 담겨 옵니다.

        if delta:
            print(delta, end="", flush=True)# flush=True: 버퍼링 없이 바로바로 출력(즉시 출력 버퍼를 비움)

    print()  # 줄바꿈
    '''
    chunk = 스트리밍으로 들어오는 한 조각
    chunk.choices = 여러 답변 후보 중 하나 이상
    chunk.choices[0] = 첫 번째 답변 후보
    chunk.choices[0].delta = 이번 조각에서 새로 생긴 메시지 부분
    chunk.choices[0].delta.content = 실제 우리가 이어서 출력할 텍스트
    '''
