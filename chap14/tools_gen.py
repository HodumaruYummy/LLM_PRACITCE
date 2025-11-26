from tavily import TavilyClient
from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from datetime import datetime
import json
import os
absolute_path = os.path.abspath(__file__) #현재 파일의 절대 경로 반환
current_path = os.path.dirname(absolute_path) # 현재 .py 파일이 있는 폴더 경로
from dotenv import load_dotenv
from langchain_community.document_loaders import WebBaseLoader

# --- .env 파일에서 API 키 로드 ---
load_dotenv()

# --- .env 또는 환경변수에서 API 키 로드 ---
google_api_key = os.getenv("GOOGLE_API_KEY")
# --- [추가] Tavily API 키 로드 ---
tavily_api_key = os.getenv("TAVILY_API_KEY")

# --- .임베딩 모델 및 저장 경로 설정
embedding = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
persist_directory = './chroma_store_gemini_v1'

# Chroma 객체 생성
vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embedding
)


@tool
def web_search(query: str):
    """
    주어진 query에 대해 웹 검색을 하고 결과를 반환한다.

    Args:
        query (str): 검색어

    returns:
        dict: 검색 결과    
    """
    client = TavilyClient()
    
    content = client.search(
        query,
        search_depth="advanced",
        included_raw_content = True,
    )

    results = content["results"]

    for result in results:
        if result["raw_content"] is None:
            try:
                result["raw_content"] = load_web_page(result["url"])
            except Exception as e:
                print(f"Error loading page: {result['url']}")
                print(e)
                result["raw_content"] = result["content"]

    resources_json_path = f'{current_path}/data/resources_{datetime.now().strftime('%Y_%m%d_%H%M%S')}.json'
    with open(resources_json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
   
    return results, resources_json_path  # 검색 결과와 JSON 파일 경로 반환

def web_page_to_document(web_page):
    # raw_content와 content 중 정보가 많은 것을 page_content로 한다.
    if len(web_page['raw_content']) > len(web_page['content']):
        page_content = web_page['raw_content']
    else:
        page_content = web_page['content']
    # 랭체인 Document로 변환
    document = Document(
        page_content=page_content,
        metadata={
            'title': web_page['title'],
            'source': web_page['url']
        }
    )

    return document

def web_page_json_to_documents(json_file):
    with open(json_file, "r", encoding='utf-8') as f:
        resources = json.load(f)

    documents = []

    for web_page in resources:
        document = web_page_to_document(web_page)
        documents.append(document)

    return documents

def split_documents(documents, chunk_size=1000, chunk_overlap=100):
    """
    문서를 지정된 크기(chunk_size)와 중첩(chunk_overlap)으로 분할합니다.
    """
    print('Splitting documents...')
    print(f"{len(documents)}개의 문서를 {chunk_size}자 크기로 중첩 {chunk_overlap}자로 분할합니다.\n")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    splits = text_splitter.split_documents(documents)

    print(f"총 {len(splits)}개의 문서로 분할되었습니다.")
    return splits

def documents_to_chroma(documents, chunk_size=1000, chunk_overlap=100):
    """
    문서를 확인하여 이미 벡터 DB에 존재하는 소스(URL 등)는 건너뛰고,
    새로운 문서만 벡터 DB(Chroma)에 추가합니다.
    """
    print("Documents를 Chroma DB에 저장 시도 중...")

    # 1. 입력된 문서들에서 소스(URL) 목록 추출
    # metadata에 'source' 키가 없는 경우를 대비해 .get() 사용
    input_urls = [doc.metadata.get('source') for doc in documents if doc.metadata.get('source')]
    
    # 2. 기존 벡터 DB에 저장된 데이터 조회 (LangChain 인터페이스 활용)
    # vectorstore.get()은 DB의 모든 메타데이터 등을 가져옵니다.
    existing_data = vectorstore.get()
    existing_urls = set()

    if existing_data['metadatas']:
        for metadata in existing_data['metadatas']:
            # 메타데이터가 존재하고 'source' 키가 있는 경우만 추출
            if metadata and 'source' in metadata:
                existing_urls.add(metadata['source'])
    
    print(f" - 기존 DB 저장 문서 수: {len(existing_data['ids'])}개")
    print(f" - 기존 DB 소스(URL) 수: {len(existing_urls)}개")

    # 3. 중복되지 않은 새로운 URL 식별 (집합 연산 차집합 활용)
    new_urls = set(input_urls) - existing_urls
    
    if not new_urls:
        print("✅ 추가할 새로운 문서가 없습니다. (모든 문서가 이미 DB에 존재함)")
        return

    print(f"✨ 새로 추가할 소스(URL) {len(new_urls)}개를 발견했습니다.")

    # 4. 새로운 URL에 해당하는 문서만 필터링
    new_documents = [doc for doc in documents if doc.metadata.get('source') in new_urls]

    if new_documents:
        # 5. 새로운 문서 분할 (Splitting)
        splits = split_documents(new_documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        # 6. 벡터 DB에 추가 (Embedding & Indexing)
        # add_documents를 호출하면 자동으로 임베딩되어 저장됩니다.
        if splits:
            vectorstore.add_documents(splits)
            print(f"🚀 {len(splits)}개의 새로운 청크가 벡터 DB에 성공적으로 저장되었습니다.")
        else:
            print("⚠ 분할된 문서가 없습니다.")
    else:
        print("처리할 새로운 문서 객체를 찾지 못했습니다.")

def add_web_pages_json_to_chroma(json_file, chunk_size=1000, chunk_overlap=100):
    """
    JSON 파일에서 웹 페이지 정보를 읽어와 Document로 변환 후,
    중복을 체크하여 Chroma DB에 저장합니다.
    """
    # tools_gen.py에 정의된 함수라고 가정 (import 필요 시 확인)
    documents = web_page_json_to_documents(json_file)
    
    if not documents:
        print("❌ JSON 파일에서 로드된 문서가 없습니다.")
        return

    documents_to_chroma(
        documents, 
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap
    )


def load_web_page(url: str):
    loader = WebBaseLoader(url, verify_ssl=False)
    content = loader.load()
    raw_content = content[0].page_content.strip()

    while '\n\n\n' in raw_content or '\t\t\t' in raw_content:
        raw_content = raw_content.replace('\n\n\n', '\n\n')
        raw_content = raw_content.replace('\t\t\t', '\t\t')
        
    return raw_content


@tool
def retrieve(query: str, top_k: int=5):
    """
    주어진 query에 대해 벡터 검색을 수행하고, 결과를 반환한다.
    """
    retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
    retrieved_docs = retriever.invoke(query)

    return retrieved_docs



if __name__ == "__main__":
    #results, resources_json_path = web_search.invoke("대한민국 핵무장 가능성")
    #print(results)
    #documents = web_page_json_to_documents(f'{current_path}/data/resources_2025_1126_172343.json')  
    #splits = split_documents(documents)
    #print(splits)
    #add_web_pages_json_to_chroma(f'{current_path}/data/resources_2025_1126_202523.json')
    retrieved_docs = retrieve.invoke({"query": "대한민국 핵무장 가능성"})
    print(retrieved_docs)
