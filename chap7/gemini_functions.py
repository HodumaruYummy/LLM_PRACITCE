import datetime
import pytz
import json
import yfinance as yf

def get_current_time(timezone: str = 'Asia/Seoul') -> str:
    """
    지정된 타임존의 현재 날짜와 시간을 JSON 형식으로 반환합니다.
    사용자가 '지금 몇 시야?', '현재 시간 알려줘', '뉴욕은 몇 시야?' 등 시간과 관련된 질문을 할 때 사용됩니다.

    Args:
        timezone (str): 'Asia/Seoul', 'America/New_York'과 같은 IANA 타임존 표준 문자열.

    Returns:
        str: {"timezone": "해당 타임존", "current_time": "YYYY-MM-DD HH:MM:SS"} 형식의 JSON 문자열.
    """
    # 디버깅을 위해 함수가 호출되었는지 터미널에 출력합니다.
    print(f"--- Function 'get_current_time' called with timezone: {timezone} ---")
    
    try:
        tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz)
        time_info = {
            "timezone": timezone,
            "current_time": now.strftime('%Y-%m-%d %H:%M:%S')
        }
        return json.dumps(time_info, ensure_ascii=False)

    except pytz.UnknownTimeZoneError:
        error_info = {
            "error": "Unknown timezone",
            "timezone_provided": timezone
        }
        return json.dumps(error_info, ensure_ascii=False)
    
def get_yf_stock_info(ticker: str):
    stock = yf.Ticker(ticker)
    info = stock.info
    print(info)

    return str(info)

def get_yf_stock_history(ticker: str, period: str):
    stock = yf.Ticker(ticker)
    history = stock.history(period=period)
    history_md = history.to_markdown()
    print(history_md)

    return history_md

def get_yf_recommendations(ticker: str):
    stock = yf.Ticker(ticker)
    recommendations = stock.recommendations
    recommendations_md=recommendations.to_markdown()
    print(recommendations_md)

    return recommendations_md

# Gemini API에 등록할 도구 목록
tools = [get_current_time, get_yf_stock_info, get_yf_stock_history, get_yf_recommendations]

# 실행 테스트용 코드
if __name__ == '__main__':
    print("현재 시간:", get_current_time())
    print(get_yf_stock_info("AAPL"))
    get_yf_stock_history('AAPL', '5d')
    get_yf_recommendations('AAPL')
