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