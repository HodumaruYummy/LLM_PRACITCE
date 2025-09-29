from openai import OpenAI # openai==1.52.2
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("Solar_api_key")
 
client = OpenAI(
    api_key=api_key,
    base_url="https://api.upstage.ai/v1"
)

def get_ai_response(messages):
    stream=client.chat.completions.create(
        model="solar-pro2",
        temperature=0.7,
        max_tokens=256,
        messages=messages,
        stream=False, #stream=True로 할 경우 for chunk in stream: 형태로 하여 처리해야함.
    )

    return stream.choices[0].message.content
messages = [
    {
        "role": "system",
        "content": "너는 내 친구야!"
    }
]
while True:
    user_input = input("User: ")
    if user_input.lower() in ['exit', 'quit']:
        print("Exiting the chat.")
        break

    messages.append({
        "role": "user",
        "content": user_input
    })
    ai_response = get_ai_response(messages)
    messages.append({"role": "assistant", "content": ai_response})
    print("AI: "+ai_response)