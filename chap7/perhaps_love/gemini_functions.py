# gemini_functions.py (updated full)

import datetime
import pytz
import json
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import io, base64
import time
import numpy as np

from dart_functions import (find_corp_code, fnltt_singl_acnt_all, extract_accounts, REPRT_CODES)
from navernews import (search_latest_news_naver, summarize_news_and_sentiment_naver, classify_news_topics_naver)

# NEW: 증권사 리포트 도구
from broker_reports import (
    search_broker_reports_naver,
    summarize_broker_reports_with_gemini,
)

def get_ticker_from_corp_name(corp_name: str) -> str:
    try:
        corp_info = find_corp_code(corp_name)
        stock_code = corp_info.get("stock_code")
        if stock_code and stock_code.strip():
            ticker = f"{stock_code}.KS"
            return json.dumps({"corp_name": corp_info["corp_name"], "ticker": ticker}, ensure_ascii=False)
        else:
            return json.dumps({"error": f"'{corp_info['corp_name']}' 종목을 찾았으나, 상장되지 않은 기업입니다."}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"티커를 찾는 중 알 수 없는 오류 발생: {e}"}, ensure_ascii=False)

def get_current_time(timezone: str = 'Asia/Seoul') -> str:
    try:
        tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz)
        return json.dumps({"timezone": timezone, "current_time": now.strftime('%Y-%m-%d %H:%M:%S')}, ensure_ascii=False)
    except pytz.UnknownTimeZoneError:
        return json.dumps({"error": "Unknown timezone", "timezone_provided": timezone}, ensure_ascii=False)

def get_yf_stock_info(ticker: str):
    stock = yf.Ticker(ticker)
    info = stock.info
    return json.dumps(info, ensure_ascii=False, default=str)

def get_yf_stock_history(ticker: str, period: str):
    stock = yf.Ticker(ticker)
    history = stock.history(period=period)
    return history.to_markdown()

def get_yf_recommendations(ticker: str):
    stock = yf.Ticker(ticker)
    recommendations = stock.recommendations
    return recommendations.to_markdown()

def get_yf_tech_chart(ticker: str, period: str = "6mo", interval: str = "1d",
                      ma_windows: list = [20, 60, 120], bb_window: int = 20, bb_std: float = 2.0) -> str:
    try:
        period = period.replace(".0", "")
        valid_ma_windows = []
        if isinstance(ma_windows, list):
            for w in ma_windows:
                try:
                    w_int = int(w)
                    if w_int > 0: valid_ma_windows.append(w_int)
                except (ValueError, TypeError): pass
        ma_windows = valid_ma_windows

        df = yf.download(tickers=ticker, period=period, interval=interval, auto_adjust=True, progress=False)
        if df is None or df.empty:
            return json.dumps({"error": "No data", "ticker": ticker, "period": period}, ensure_ascii=False)

        df = df.copy()
        for w in ma_windows: df[f"SMA{w}"] = df["Close"].rolling(w).mean()
        df["BB_MID"] = df["Close"].rolling(bb_window).mean()
        df["BB_STD"] = df["Close"].rolling(bb_window).std(ddof=0)
        df["BB_UPPER"] = df["BB_MID"] + bb_std * df["BB_STD"]
        df["BB_LOWER"] = df["BB_MID"] - bb_std * df["BB_STD"]

        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        ax.plot(df.index, df["Close"], label="Close")
        for w in ma_windows: ax.plot(df.index, df[f"SMA{w}"], label=f"SMA {w}")
        ax.plot(df.index, df["BB_UPPER"], linestyle="--", label=f"BB Upper ({bb_window}, {bb_std}σ)")
        ax.plot(df.index, df["BB_MID"], linestyle="--", label="BB Middle")
        ax.plot(df.index, df["BB_LOWER"], linestyle="--", label="BB Lower")
        ax.set_title(f"{ticker} — MAs & Bollinger Bands"); ax.set_xlabel("Date"); ax.set_ylabel("Price")
        ax.grid(True, alpha=0.3); ax.legend(loc="best"); fig.tight_layout()

        buf = io.BytesIO(); fig.savefig(buf, format="png"); plt.close(fig); buf.seek(0)
        image_b64 = base64.b64encode(buf.read()).decode("utf-8")

        last_close = float(df["Close"].iloc[-1])
        sma_values = {str(w): (None if pd.isna(df[f'SMA{w}'].iloc[-1]) else float(df[f'SMA{w}'].iloc[-1])) for w in ma_windows}
        bb_values = {"mid": None if pd.isna(df["BB_MID"].iloc[-1]) else float(df["BB_MID"].iloc[-1]),
                     "upper": None if pd.isna(df["BB_UPPER"].iloc[-1]) else float(df["BB_UPPER"].iloc[-1]),
                     "lower": None if pd.isna(df["BB_LOWER"].iloc[-1]) else float(df["BB_LOWER"].iloc[-1])}
        return json.dumps({"ticker": ticker, "last": last_close, "sma": sma_values, "bb": bb_values, "image_base64": image_b64}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)

def get_dart_indicators_quarterly(corp_name: str, years: int = 5, fs_div: str = "CFS", ticker: str | None = None) -> str:
    try:
        info = find_corp_code(corp_name)
        corp_code = info["corp_code"]
        indicators = {}
        this_year = datetime.datetime.now().year
        start_year = this_year - years + 1

        price_df = None
        if ticker:
            price_df = yf.download(ticker, period=f"{years+1}y", interval="1d", auto_adjust=True, progress=False)

        for y in range(start_year, this_year + 1):
            for reprt_code, _label in REPRT_CODES:
                time.sleep(0.2)
                df = fnltt_singl_acnt_all(corp_code, y, reprt_code, fs_div=fs_div)
                if df is None or df.empty: continue

                accts = extract_accounts(df, ["당기순이익", "지배주주순이익", "자본총계", "자산총계", "기본주당이익", "총자산이익률", "자기자본이익률"])
                eps = accts.get("기본주당이익"); roe = accts.get("자기자본이익률"); roa = accts.get("총자산이익률")
                ni = accts.get("지배주주순이익") or accts.get("당기순이익"); eq = accts.get("자본총계"); at = accts.get("자산총계")
                if roe is None and ni and eq: roe = (ni / eq) * 100
                if roa is None and ni and at: roa = (ni / at) * 100

                month = {"11011": 3, "11012": 6, "11013": 9, "11014": 12}[reprt_code]
                q_end = pd.Timestamp(year=y, month=month, day=1) + pd.offsets.MonthEnd(1)

                price, per = None, None
                if ticker and eps and price_df is not None and not price_df.empty:
                    px = price_df.loc[:q_end]
                    if not px.empty:
                        price = float(px["Close"].iloc[-1])
                        per = price / eps if eps != 0 else 0

                q_end_str = q_end.strftime('%Y-%m-%d')
                indicators[q_end_str] = {"price": price, "eps": eps, "per_ttm": per, "roe_ttm_percent": roe, "roa_ttm_percent": roa}

        if not indicators:
            return json.dumps({"error": "해당 기간에 대한 분기 데이터가 없습니다.", "corp_name": corp_name}, ensure_ascii=False)
        return json.dumps({"ticker": ticker or corp_name, "indicators": indicators}, ensure_ascii=False, default=lambda x: None if pd.isna(x) else x)
    except Exception as e:
        return json.dumps({"error": str(e), "corp_name": corp_name}, ensure_ascii=False)

def get_yf_tech_values(ticker: str, period: str = "6mo", interval: str = "1d", ma_windows: list = [20, 60, 120], bb_window: int = 20, bb_std: float = 2.0) -> str:
    try:
        period = period.replace(".0", "")
        valid_ma_windows = []
        if isinstance(ma_windows, list):
            for w in ma_windows:
                try:
                    w_int = int(w)
                    if w_int > 0: valid_ma_windows.append(w_int)
                except (ValueError, TypeError): pass
        ma_windows = valid_ma_windows
        df = yf.download(tickers=ticker, period=period, interval=interval, auto_adjust=True, progress=False)
        if df is None or df.empty: return json.dumps({"error": "No data", "ticker": ticker}, ensure_ascii=False)
        df = df.copy()
        for w in ma_windows: df[f"SMA{w}"] = df["Close"].rolling(w).mean()
        df["BB_MID"] = df["Close"].rolling(bb_window).mean()
        df["BB_STD"] = df["Close"].rolling(bb_window).std(ddof=0)
        df["BB_UPPER"] = df["BB_MID"] + bb_std * df["BB_STD"]
        df["BB_LOWER"] = df["BB_MID"] - bb_std * df["BB_STD"]
        last_close = float(df["Close"].iloc[-1])
        sma_values = {str(w): (None if pd.isna(df[f'SMA{w}'].iloc[-1]) else float(df[f'SMA{w}'].iloc[-1])) for w in ma_windows}
        bb_values = {"mid": None if pd.isna(df["BB_MID"].iloc[-1]) else float(df["BB_MID"].iloc[-1]),
                     "upper": None if pd.isna(df["BB_UPPER"].iloc[-1]) else float(df["BB_UPPER"].iloc[-1]),
                     "lower": None if pd.isna(df["BB_LOWER"].iloc[-1]) else float(df["BB_LOWER"].iloc[-1])}
        return json.dumps({"ticker": ticker, "last": last_close, "sma": sma_values, "bb": bb_values}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)

tools = [
    # 티커
    get_ticker_from_corp_name,
    # 시간
    get_current_time,
    # yfinance
    get_yf_stock_info, get_yf_stock_history, get_yf_recommendations,
    get_yf_tech_chart, get_yf_tech_values,
    # DART
    get_dart_indicators_quarterly,
    # 뉴스
    search_latest_news_naver, summarize_news_and_sentiment_naver, classify_news_topics_naver,
    # 리포트 (NEW)
    search_broker_reports_naver, summarize_broker_reports_with_gemini,
]
