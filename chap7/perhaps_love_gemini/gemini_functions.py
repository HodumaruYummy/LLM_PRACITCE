# gemini_functions.py
from __future__ import annotations
import json
from datetime import date, timedelta

# 기존에 우리가 만들었던 기능들을 가져옵니다.
from dart_functions import get_ticker_from_name_fuzzy, get_corp_outline, get_dart_indicators_quarterly, get_historical_price, normalize_financial_payload
from navernews import search_latest_news_naver

def search_company_info(company_name: str) -> str:
    """
    회사의 DART(공시) 기반 공식적인 개요 정보를 조회합니다. 
    회사의 대표자, 설립일, 주소, 주요 사업 등을 알고 싶을 때 사용하세요.
    Args:
        company_name (str): 조회할 회사의 이름 (예: '삼성전자')
    """
    hit = get_ticker_from_name_fuzzy(company_name)
    if not hit.get("best"):
        return json.dumps({"error": f"'{company_name}' 기업을 찾을 수 없습니다."})
    
    corp_code = hit["best"]["corp_code"]
    outline = get_corp_outline(corp_code)

    if outline.get("status") != "000":
        return json.dumps({"error": outline.get("message")})

    return json.dumps(outline, ensure_ascii=False)

def search_financial_info(company_name: str, years: int = 1) -> str:
    """
    회사의 분기별 실적, 재무 지표(매출, 영업이익, PER, ROE 등)를 조회합니다.
    Args:
        company_name (str): 조회할 회사의 이름 (예: '삼성전자')
        years (int): 조회할 기간 (기본값: 1년)
    """
    hit = get_ticker_from_name_fuzzy(company_name)
    if not hit.get("best"):
        return json.dumps({"error": f"'{company_name}' 기업을 찾을 수 없습니다."})
    
    best_match = hit["best"]
    payload = get_dart_indicators_quarterly(corp_name=best_match["corp_name"], symbol=best_match["stock_code"], years=years)
    
    if payload.get("error"):
        return json.dumps(payload)
    
    _, df = normalize_financial_payload(payload)
    if df.empty:
        return json.dumps({"error": "재무 정보를 찾을 수 없습니다."})

    # Gemini가 이해하기 쉽도록 최신 4분기 데이터만 JSON으로 반환
    return df.head(4).to_json(orient='records', force_ascii=False, indent=4)

def search_news_articles(query: str, limit: int = 5) -> str:
    """
    특정 주제나 회사에 대한 최신 뉴스 기사를 검색합니다. 
    최신 동향, 이슈, 시장 반응 등을 알고 싶을 때 사용하세요.
    Args:
        query (str): 검색할 키워드 (예: '삼성전자 HBM', '카카오 실적 발표')
        limit (int): 가져올 기사 수 (기본값: 5)
    """
    result = search_latest_news_naver(query=query, display=limit, recent_days=30)
    if not result.get("items"):
        return json.dumps({"error": f"'{query}'에 대한 뉴스를 찾을 수 없습니다."})
    
    # Gemini에게는 제목, 링크, 요약, 감성분석 결과만 간단히 전달
    simplified_items = [{
        "title": item.get("title"),
        "link": item.get("originallink") or item.get("link"),
    } for item in result["items"][:limit]]
    
    return json.dumps(simplified_items, ensure_ascii=False, indent=4)

def get_stock_price(company_name: str, target_date_str: str) -> str:
    """
    특정 회사의 특정 날짜 주가를 조회합니다. '오늘', '어제', '2023-10-14'와 같은 날짜 형식을 사용하세요.
    Args:
        company_name (str): 조회할 회사의 이름 (예: '삼성전자')
        target_date_str (str): 조회할 날짜 (YYYY-MM-DD 형식 또는 '오늘', '어제')
    """
    hit = get_ticker_from_name_fuzzy(company_name)
    if not hit.get("best"):
        return json.dumps({"error": f"'{company_name}' 기업을 찾을 수 없습니다."})
    
    stock_code = hit["best"]["stock_code"]
    if not stock_code or not stock_code.strip():
        return json.dumps({"error": f"'{company_name}'은(는) 상장사가 아닙니다."})

    target_date = date.today()
    if "어제" in target_date_str:
        target_date = date.today() - timedelta(days=1)
    else:
        try:
            target_date = date.fromisoformat(target_date_str)
        except (ValueError, TypeError):
            pass # 오늘 날짜 기본값 사용
            
    ticker = f"{stock_code}.KS"
    result = get_historical_price(ticker, target_date)
    if result.get("error"):
        ticker_kq = ticker.replace(".KS", ".KQ")
        result = get_historical_price(ticker_kq, target_date)

    return json.dumps(result, ensure_ascii=False)

# Gemini 모델이 사용할 도구 목록
tools = [
    search_company_info,
    search_financial_info,
    search_news_articles,
    get_stock_price,
]