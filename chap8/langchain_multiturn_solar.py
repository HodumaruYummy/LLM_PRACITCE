import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()
llm = ChatOpenAI(
    model="solar-pro2",
    api_key=os.getenv("UPSTAGE_API_KEY"), # .env에서 키 로드
    base_url="https://api.upstage.ai/v1"
)

messages=[SystemMessage("너는 사용자를 친절하게 이모지를 사용하여 도와주는 상담사야")]

print("--- 챗봇 시작 (종료: 'exit') ---")

while True:
    user_input =input("사용자: ")

    if user_input.lower() =="exit":
        print("---챗봇 종료 ---")
        break

    messages.append(HumanMessage(user_input))

    ai_response = llm.invoke(messages)

    messages.append(ai_response)

    print("AI:" + ai_response.content)
    