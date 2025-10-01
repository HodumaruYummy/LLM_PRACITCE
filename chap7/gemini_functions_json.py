import datetime
import pytz
import json
from typing import Dict, Union

# --- 상수 정의 ---
KEY_TIMEZONE = "timezone"
KEY_CURRENT_TIME = "current_time"
KEY_ERROR = "error"
KEY_TIMEZONE_PROVIDED = "timezone_provided"

def get_current_time(timezone: str = 'Asia/Seoul') -> str:
    """
    지정된 타임존의 현재 날짜와 시간을 JSON 형식으로 반환합니다.

    Args:
        timezone (str): 예) 'Asia/Seoul', 'America/New_York'와 같은 타임존 문자열.

    Returns:
        str: {"timezone": "...", "current_time": "..."} 또는 오류 정보가 담긴 JSON 문자열.
    """
    try:
        tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz)

        time_info: Dict[str, str] = {
            KEY_TIMEZONE: timezone,
            KEY_CURRENT_TIME: now.strftime('%Y-%m-%d %H:%M:%S')
        }
        return json.dumps(time_info, ensure_ascii=False)

    except pytz.UnknownTimeZoneError:
        error_info: Dict[str, str] = {
            KEY_ERROR: "Unknown timezone",
            KEY_TIMEZONE_PROVIDED: timezone
        }
        return json.dumps(error_info, ensure_ascii=False)

# Gemini API 등에 등록할 도구 목록
tools = [get_current_time]

# 모듈 단독 실행 시 테스트
if __name__ == '__main__':
    print("서울 현재 시간:", get_current_time())
    print("뉴욕 현재 시간:", get_current_time(timezone='America/New_York'))
    print("잘못된 타임존:", get_current_time(timezone='Invalid/Timezone'))