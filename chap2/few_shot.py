from openai import OpenAI # openai==1.52.2
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("Solar_api_key")
 
client = OpenAI(
    api_key=api_key,
    base_url="https://api.upstage.ai/v1"
)
 
stream = client.chat.completions.create(
    model="solar-pro2",
    temperature=0.7,
    max_tokens=256,
    messages=[
        {
            "role": "system",
            "content": "너는 요리 전문가 안성재 쉐프야!"
        },
        {
            "role": "user",
            "content": "짜파게티를 어떻게 끓여?"
        },
                {
            "role": "assistant",
            "content": "Even하게 Feel 가는대로 끓여"
        },
                {
            "role": "user",
            "content": "신라면 어떻게 끓여?"
        },
                {
            "role": "assistant",
            "content": "콩나물 팍팍 넣어서 끊여"
        },
        {
            "role": "user",
            "content": "불닭볶음면을 맛있게 끓이는 방법을 알려줘"
        }
    ],
    stream=True,
)
 
for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
 
# Use with stream=False
# print(stream.choices[0].message.content)

'''
1. stream=False (기본 모드)

동작 방식
서버가 전체 답변을 다 생성할 때까지 기다렸다가 한 번에 전체 응답을 돌려줍니다.
코드에서 resp.choices[0].message.content 로 바로 접근할 수 있습니다.

장점
코드가 단순함 (resp.choices[0].message.content만 출력)
최종 완성된 응답을 한 번에 다룰 수 있음

단점
답변이 길면 기다리는 시간이 김 (모든 토큰을 다 생성해야 전달됨)
사용자에게 “지연”이 느껴질 수 있음

2. stream=True (스트리밍 모드)

동작 방식

답변을 토큰 단위로 쪼개서 바로바로 전송합니다.
따라서 for chunk in stream: 반복문으로 토큰 조각을 순서대로 받게 됩니다.
이때 chunk.choices[0].delta.content에 새로 추가된 부분이 들어있습니다.

장점
사용자가 답변을 실시간으로 받아볼 수 있음 → 채팅 앱, 대화형 UI에 적합
긴 응답도 기다리지 않고 바로 표시 시작 가능

단점
코드가 조금 복잡함 (for chunk in stream: 루프 필요)
최종 전체 문자열을 원한다면 조각들을 모아서 합쳐야 함


'''