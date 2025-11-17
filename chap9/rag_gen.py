# --- packages ---
# !pip install -q langchain-google-genai langchain_chroma langchain-core langchain python-dotenv

import os
from typing import List
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnableMap
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

# --- 1. API 키 설정 ---
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("환경 변수 'GOOGLE_API_KEY'를 설정해주세요. (.env 파일 확인)")

# (참고) Colab/Codespaces용 키 로더는 .env 로직과 통합되어 있으므로 
# load_dotenv()가 대부분의 환경을 처리합니다. 원본 코드를 유지합니다.
try:
    from google.colab import userdata
    if not GOOGLE_API_KEY: # .env에 키가 없을 때만 Colab 시도
        GOOGLE_API_KEY = userdata.get('GOOGLE_API_KEY')
        if GOOGLE_API_KEY:
            print("Google Colab 환경에서 API 키를 로드했습니다.")
except ImportError:
    pass # Colab이 아니면 무시

if not GOOGLE_API_KEY:
     print("환경 변수 'GOOGLE_API_KEY'를 찾을 수 없습니다.")
else:
     print("Google API 키를 로드했습니다.")

if 'GOOGLE_API_KEY' not in os.environ and GOOGLE_API_KEY:
    os.environ['GOOGLE_API_KEY'] = GOOGLE_API_KEY

# --- 2. 모델 선언 (Gemini) ---
# 임베딩 모델 선언하기
embedding = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004", 
    api_key=GOOGLE_API_KEY
)

# 언어 모델 불러오기
chat = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", # 원본 모델 유지
    api_key=GOOGLE_API_KEY,
    temperature=0.0
) 

# --- 3. 벡터 스토어 및 리트리버 ---
print("Loading existing Chroma store")
persist_directory = r'C:\Users\ziclp\OneDrive\Desktop\LLM Assignment\1week\PRACTICE1\chroma_store'

vectorstore = Chroma(
    persist_directory=persist_directory, 
    embedding_function=embedding
)

# ⚠️ [플레이스홀더 1] 도시 감지 로직 (필요시 구현)
def detect_city_from_query(query: str) -> str:
    # 예: 쿼리에서 '서울', '부산' 등 도시명 추출
    print(f"[Debug] Detecting city from: {query}")
    if "부산" in query:
        return "부산"
    # ... (실제 도시 감지 로직 구현) ...
    return "서울" # 기본값

# ⚠️ [플레이스홀더 2] 도시 필터 리트리버 생성 (필요시 구현)
def city_retriever(city: str):
    # 'city' 메타데이터를 기반으로 필터링하는 리트리버 생성
    print(f"[Debug] Creating retriever for city: {city}")
    return vectorstore.as_retriever(
        search_kwargs={'k': 3, 'filter': {'city': city}}
    )

# --- 4. 프롬프트 (컨텍스트 없으면 명확히 선언 + 도시 일탈 금지 규칙) ---
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "아래 문맥(Context)에 근거해 한국어로만 간결하게 답하라. "
     "문맥에 없으면 '제공된 문서에는 해당 정보가 없습니다.'라고 답하라.\n"
     "반드시 {city} 관련 내용만 답하고, 다른 도시는 언급하지 마라.\n\n"
     "Context:\n{context}"),
    MessagesPlaceholder("messages"),
    ("human", "{query}")
])

# --- 5. 문서 결합(stuffing) ---
def stuff(docs: List[Document]) -> str:
    if not docs:
        return ""  
    return "\n\n".join(d.page_content for d in docs)

# --- 6. 도시 감지 → 도시별 리트리브 → 컨텍스트/도시 주입 ---
def retrieve_with_city(inputs: dict) -> dict:
    q = inputs.get("query", "")
    messages = inputs.get("messages", [])
    
    city = detect_city_from_query(q)
    retr = city_retriever(city)  
    docs = retr.invoke(q)        
    
    print(f"[Debug] Retrieved {len(docs)} docs for query '{q}' with city '{city}'")

    return {
        "city": city,
        "context": docs,        
        "messages": messages,
        "query": q
    }

# --- 7. LCEL 체인 구성 (기존 document_chain, query_augmentation_chain 대체) ---
document_chain = (
    RunnableLambda(retrieve_with_city) |
    RunnableMap({
        "city":     RunnableLambda(lambda x: x["city"]),
        "context":  RunnableLambda(lambda x: stuff(x["context"])),
        "messages": RunnableLambda(lambda x: x.get("messages", [])),
        "query":    RunnableLambda(lambda x: x["query"]),
    }) |
    prompt |
    chat |
    StrOutputParser() # 원본과 1:1 대응 (문자열 반환)
)

print(f"✅ Gemini LLM ({getattr(chat, 'model', '')}) 기반 문서 체인(도시 필터 RAG) 설정 완료.")

# --- (선택 사항) 테스트 실행 ---
# if __name__ == "__main__":
#     chat_history = [
#         HumanMessage(content="서울시 정책에 대해 알려줘"),
#         AIMessage(content="서울시의 어떤 정책이 궁금하신가요?")
#     ]
# 
#     new_query = "주요 복지 혜택은?"
#     chat_history.append(HumanMessage(content=new_query))
# 
#     response = document_chain.invoke({
#         "messages": chat_history,
#         "query": new_query
#     })
#     
#     print("\n--- RAG Response ---")
#     print(response)