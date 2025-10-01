import datetime
import pytz
import json

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

# Gemini API에 등록할 도구 목록
tools = [get_current_time]

# 실행 테스트용 코드
if __name__ == '__main__':
    print("현재 시간:", get_current_time())

