import pytz
import yfinance as yf
import pandas as pd
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import json # ‼️ JSON으로 안정적인 반환을 위해 추가

# (터미널/Colab에서 pip install yfinance pandas pytz pydantic 설치 필요)

# --- Tool 1: get_current_time (변경 없음) ---

@tool
def get_current_time(timezone: str, location: str) -> str:
    """현재 시각을 반환하는 함수."""
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        result = f'{timezone} ({location}) 현재시각 {now}'
        print(f"Tool Executed (get_current_time): {result}")
        return result
    except pytz.UnknownTimeZoneError:
        return f"알 수 없는 타임존: {timezone}"

# --- (공용) 주식 도구에서 사용할 Pydantic 입력 모델 ---

class StockTickerInput(BaseModel):
    """주식 도구에서 공통으로 사용할 티커 입력 모델"""
    ticker: str = Field(description="주가 정보를 조회할 종목의 티커 심볼 (예: 'AAPL', '005930.KS')")

class StockHistoryInput(BaseModel):
    """주가 추이 조회시 사용할 입력 모델"""
    ticker: str = Field(description="주가 정보를 조회할 종목의 티커 심볼")
    period: str = Field(
        description="조회할 기간 (예: '1mo', '3mo', '1y', '5y', 'ytd')", 
        default='1mo' # 기본값을 1달로 설정
    )

# --- (신규) Tool 2: get_stock_info (기업 상세 정보) ---
# 기존 get_stock_price를 대체합니다.

@tool
def get_stock_info(inputs: StockTickerInput) -> str:
    """
    주어진 티커 심볼의 상세한 기업 정보(현재가, 시가총액, 기업 요약 등)를 JSON 문자열로 반환합니다.
    """
    try:
        stock = yf.Ticker(inputs.ticker)
        info = stock.info # yfinance에서 제공하는 방대한 정보 딕셔너리

        if not info or info.get('quoteType') == 'NONE':
             return json.dumps({"error": f"티커 '{inputs.ticker}'에 대한 정보를 찾을 수 없습니다."})

        # LLM에게 전달할 핵심 정보만 선별
        key_info = {
            "ticker": inputs.ticker,
            "shortName": info.get('shortName', 'N/A'),
            "currentPrice": info.get('currentPrice', info.get('previousClose', 'N/A')),
            "currency": info.get('currency', 'N/A'),
            "marketCap": info.get('marketCap', 'N/A'),
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "longBusinessSummary": info.get('longBusinessSummary', 'N/A')[:500] + "..." # 요약은 너무 길 수 있으므로 500자 제한
        }
        
        print(f"Tool Executed (get_stock_info): {inputs.ticker}")
        # ‼️ LLM이 안정적으로 파싱할 수 있도록 JSON 문자열로 반환
        return json.dumps(key_info, ensure_ascii=False) 
        
    except Exception as e:
        return json.dumps({"error": f"'{inputs.ticker}'의 기업 정보 조회 중 오류 발생: {str(e)}"})

# --- (신규) Tool 3: get_stock_history (주가 추이) ---

@tool
def get_stock_history(inputs: StockHistoryInput) -> str:
    """
    주어진 티커 심볼의 지정된 기간 동안의 주가 추이 (시작, 끝, 최고, 최저)를 JSON 문자열로 반환합니다.
    """
    try:
        stock = yf.Ticker(inputs.ticker)
        hist = stock.history(period=inputs.period)
        
        if hist.empty:
            return json.dumps({"error": f"'{inputs.ticker}'의 {inputs.period}간 주가 기록을 찾을 수 없습니다."})
        
        # DataFrame을 직접 처리하지 않고, LLM이 이해하기 쉬운 요약 정보로 가공
        start_price = hist['Close'].iloc[0]
        end_price = hist['Close'].iloc[-1]
        min_price = hist['Low'].min()
        max_price = hist['High'].max()
        change_percent = ((end_price - start_price) / start_price) * 100

        history_summary = {
            "ticker": inputs.ticker,
            "period": inputs.period,
            "startDate": hist.index[0].strftime('%Y-%m-%d'),
            "endDate": hist.index[-1].strftime('%Y-%m-%d'),
            "startPrice": f"{start_price:.2f}",
            "endPrice": f"{end_price:.2f}",
            "periodLow": f"{min_price:.2f}",
            "periodHigh": f"{max_price:.2f}",
            "changePercent": f"{change_percent:.2f}%"
        }
        
        print(f"Tool Executed (get_stock_history): {inputs.ticker} for {inputs.period}")
        return json.dumps(history_summary, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"error": f"'{inputs.ticker}'의 주가 추이 조회 중 오류 발생: {str(e)}"})

# --- (신규) Tool 4: get_stock_recommendations (애널리스트 추천) ---

@tool
def get_stock_recommendations(inputs: StockTickerInput) -> str:
    """
    주어진 티커 심볼에 대한 애널리스트의 최신 추천(recommendation) 요약을 JSON 문자열로 반환합니다.
    """
    try:
        stock = yf.Ticker(inputs.ticker)
        
        # 'recommendations'는 DataFrame을 반환, 없을 수도 있음
        recs = stock.recommendations
        
        if recs is None or recs.empty:
            # 'info'에 있는 'recommendationKey' (예: 'buy', 'hold')를 대신 사용
            rec_key = stock.info.get('recommendationKey', '정보 없음')
            return json.dumps({
                "ticker": inputs.ticker,
                "recommendationSummary": rec_key
            })
        
        # 최신 5개 추천을 DataFrame에서 추출
        latest_recs = recs.tail(5).reset_index() # 인덱스 리셋
        
        # DataFrame을 LLM이 사용하기 쉬운 JSON (dict 리스트) 형태로 변환
        recs_list = latest_recs[['Date', 'Firm', 'To Grade']].to_dict('records')
        
        # 날짜(Date) 객체를 문자열로 변환
        for rec in recs_list:
            if isinstance(rec['Date'], pd.Timestamp):
                rec['Date'] = rec['Date'].strftime('%Y-%m-%d')

        result = {
            "ticker": inputs.ticker,
            "latestRecommendations": recs_list
        }
        
        print(f"Tool Executed (get_stock_recommendations): {inputs.ticker}")
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        # yfinance가 종종 'recommendations'에 대해 오류를 일으킴. info의 'recommendationKey'로 대체.
        try:
            rec_key = yf.Ticker(inputs.ticker).info.get('recommendationKey', 'N/A')
            return json.dumps({"ticker": inputs.ticker, "recommendationSummary": rec_key})
        except Exception:
            return json.dumps({"error": f"'{inputs.ticker}'의 추천 정보 조회 중 오류 발생: {str(e)}"})

# --- 메인 앱에서 import할 리스트 및 딕셔너리 (업데이트됨) ---

all_tools = [
    get_current_time, 
    get_stock_info,           # ⭐️ 신규 (get_stock_price 대체)
    get_stock_history,        # ⭐️ 신규
    get_stock_recommendations # ⭐️ 신규
]

tool_dict = {
    "get_current_time": get_current_time,
    "get_stock_info": get_stock_info,
    "get_stock_history": get_stock_history,
    "get_stock_recommendations": get_stock_recommendations
}