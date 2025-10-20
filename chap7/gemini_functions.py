import datetime
import pytz
import json
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import io, base64
import time           
import numpy as np
from dart_functions import find_corp_code, fnltt_singl_acnt_all, extract_accounts, REPRT_CODES


def get_current_time(timezone: str = 'Asia/Seoul') -> str:
    print(f"--- Function 'get_current_time' called with timezone: {timezone} ---")
    try:
        tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz)
        time_info = {"timezone": timezone, "current_time": now.strftime('%Y-%m-%d %H:%M:%S')}
        return json.dumps(time_info, ensure_ascii=False)
    except pytz.UnknownTimeZoneError:
        error_info = {"error": "Unknown timezone", "timezone_provided": timezone}
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
    recommendations_md = recommendations.to_markdown()
    print(recommendations_md)
    return recommendations_md

# -----------------------------
# (NEW) 기술지표 차트 생성 함수
# -----------------------------
def get_yf_tech_chart(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    ma_windows: list[int] = [20, 60, 120],
    bb_window: int = 20,
    bb_std: float = 2.0
) -> str:
    """
    yfinance로 가격을 받아 이동평균선(기본 20/60/120)과 볼린저밴드(기본 20, 2σ)를
    하나의 차트로 그려 base64 PNG와 최신 지표값을 JSON 문자열로 반환합니다.
    { "image_base64": "...", "last": ..., "sma": {...}, "bb": {...} }
    """
    try:
        df = yf.download(
            tickers=ticker, period=period, interval=interval,
            auto_adjust=True, progress=False
        )
        if df is None or df.empty:
            return json.dumps({"error": "No data", "ticker": ticker, "period": period, "interval": interval}, ensure_ascii=False)

        # 지표 계산
        df = df.copy()
        for w in ma_windows:
            df[f"SMA{w}"] = df["Close"].rolling(w).mean()

        df["BB_MID"] = df["Close"].rolling(bb_window).mean()
        df["BB_STD"] = df["Close"].rolling(bb_window).std(ddof=0)
        df["BB_UPPER"] = df["BB_MID"] + bb_std * df["BB_STD"]
        df["BB_LOWER"] = df["BB_MID"] - bb_std * df["BB_STD"]

        # 차트
        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        ax.plot(df.index, df["Close"], label="Close")
        for w in ma_windows:
            ax.plot(df.index, df[f"SMA{w}"], label=f"SMA {w}")
        ax.plot(df.index, df["BB_UPPER"], linestyle="--", label=f"BB Upper ({bb_window}, {bb_std}σ)")
        ax.plot(df.index, df["BB_MID"], linestyle="--", label="BB Middle")
        ax.plot(df.index, df["BB_LOWER"], linestyle="--", label="BB Lower")

        ax.set_title(f"{ticker} — MAs & Bollinger Bands")
        ax.set_xlabel("Date")
        ax.set_ylabel("Price")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        image_b64 = base64.b64encode(buf.read()).decode("utf-8")

        # 최신값 요약
        last_close = float(df["Close"].iloc[-1])
        sma_values = {}
        for w in ma_windows:
            val = df[f"SMA{w}"].iloc[-1]
            sma_values[str(w)] = None if pd.isna(val) else float(val)

        bb_mid = df["BB_MID"].iloc[-1]
        bb_up = df["BB_UPPER"].iloc[-1]
        bb_low = df["BB_LOWER"].iloc[-1]
        bb_values = {
            "mid": None if pd.isna(bb_mid) else float(bb_mid),
            "upper": None if pd.isna(bb_up) else float(bb_up),
            "lower": None if pd.isna(bb_low) else float(bb_low),
            "window": bb_window,
            "std_multiplier": bb_std
        }

        payload = {
            "ticker": ticker,
            "period": period,
            "interval": interval,
            "last": last_close,
            "sma": sma_values,
            "bb": bb_values,
            "image_base64": image_b64
        }
        return json.dumps(payload, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)

# -----------------------------
# (NEW) 지표 최신 값만 반환 (차트 없음)
# -----------------------------
def get_yf_tech_values(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    ma_windows: list[int] = [20, 60, 120],
    bb_window: int = 20,
    bb_std: float = 2.0
) -> str:
    """
    차트 없이 이동평균선/볼린저밴드의 최신 값만 JSON으로 반환합니다.
    """
    try:
        df = yf.download(
            tickers=ticker, period=period, interval=interval,
            auto_adjust=True, progress=False
        )
        if df is None or df.empty:
            return json.dumps({"error": "No data", "ticker": ticker, "period": period, "interval": interval}, ensure_ascii=False)

        df = df.copy()
        for w in ma_windows:
            df[f"SMA{w}"] = df["Close"].rolling(w).mean()

        df["BB_MID"] = df["Close"].rolling(bb_window).mean()
        df["BB_STD"] = df["Close"].rolling(bb_window).std(ddof=0)
        df["BB_UPPER"] = df["BB_MID"] + bb_std * df["BB_STD"]
        df["BB_LOWER"] = df["BB_MID"] - bb_std * df["BB_STD"]

        last_close = float(df["Close"].iloc[-1])
        sma_values = {str(w): (None if pd.isna(df[f'SMA{w}'].iloc[-1]) else float(df[f'SMA{w}'].iloc[-1])) for w in ma_windows}
        bb_values = {
            "mid": None if pd.isna(df["BB_MID"].iloc[-1]) else float(df["BB_MID"].iloc[-1]),
            "upper": None if pd.isna(df["BB_UPPER"].iloc[-1]) else float(df["BB_UPPER"].iloc[-1]),
            "lower": None if pd.isna(df["BB_LOWER"].iloc[-1]) else float(df["BB_LOWER"].iloc[-1]),
            "window": bb_window,
            "std_multiplier": bb_std
        }

        return json.dumps({
            "ticker": ticker,
            "period": period,
            "interval": interval,
            "last": last_close,
            "sma": sma_values,
            "bb": bb_values
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)

def get_dart_indicators_quarterly(
    corp_name: str,
    years: int = 5,
    fs_div: str = "CFS",           # CFS(연결) / OFS(개별)
    ticker: str | None = None      # PER 계산을 원하면 yfinance용 티커(예: "005930.KS") 전달
) -> str:
    """
    DART 공시(단일회사 전체 재무제표)를 기반으로 최근 N년(기본 5년) 분기 지표 테이블을 만듭니다.
    - EPS: '기본주당이익'
    - ROE: '자기자본이익률' or (당기순이익/자본총계)
    - ROA: '총자산이익률' or (당기순이익/자산총계)
    - PER: (선택) 분기말 종가 / EPS  (ticker를 넘긴 경우에만 계산)
    반환: markdown 문자열(표)
    """
    try:
        # corp_code 조회
        info = find_corp_code(corp_name)
        corp_code = info["corp_code"]

        rows = []
        this_year = datetime.datetime.now().year
        start_year = this_year - years + 1

        # 분기말 가격 데이터(선택)
        price_df = None
        if ticker:
            # years+1년 정도 여유로 다운로드
            price_df = yf.download(
                ticker, period=f"{years+1}y", interval="1d",
                auto_adjust=True, progress=False
            )

        # 1Q/2Q/3Q/4Q 순서대로 훑기
        for y in range(start_year, this_year + 1):
            for reprt_code, _label in REPRT_CODES:
                time.sleep(0.2)  # DART rate limit 친화적

                df = fnltt_singl_acnt_all(corp_code, y, reprt_code, fs_div=fs_div)
                if df is None or df.empty:
                    continue

                # 필요한 계정 추출
                accts = extract_accounts(df, [
                    "당기순이익", "지배주주순이익",
                    "자본총계", "자산총계",
                    "기본주당이익", "총자산이익률", "자기자본이익률"
                ])

                # 기본 지표
                eps = accts.get("기본주당이익")
                roe = accts.get("자기자본이익률")
                roa = accts.get("총자산이익률")

                # 직접 제공되지 않으면 계산
                ni = accts.get("지배주주순이익") or accts.get("당기순이익")
                eq = accts.get("자본총계")
                at = accts.get("자산총계")

                if roe is None and ni not in (None, 0) and eq not in (None, 0):
                    try:
                        roe = float(ni) / float(eq)
                    except Exception:
                        roe = None
                if roa is None and ni not in (None, 0) and at not in (None, 0):
                    try:
                        roa = float(ni) / float(at)
                    except Exception:
                        roa = None

                # 분기말 날짜(1Q:3/31, 2Q:6/30, 3Q:9/30, 4Q:12/31)
                month = {"11011": 3, "11012": 6, "11013": 9, "11014": 12}[reprt_code]
                q_end = pd.Timestamp(year=y, month=month, day=1) + pd.offsets.MonthEnd(1)

                # PER (선택)
                price = None
                per = None
                if ticker and eps not in (None, 0) and price_df is not None and not price_df.empty:
                    px = price_df.loc[:q_end]
                    if not px.empty:
                        price = float(px["Close"].iloc[-1])
                        try:
                            per = float(price) / float(eps) if float(eps) != 0 else None
                        except Exception:
                            per = None

                rows.append({
                    "QuarterEnd": q_end.date(),
                    "Price": price,
                    "EPS": None if eps is None else float(eps),
                    "PER": per,
                    "ROE": None if roe is None else float(roe),
                    "ROA": None if roa is None else float(roa),
                    "NetIncome": ni,
                    "Equity": eq,
                    "Assets": at
                })

        if not rows:
            return "해당 기간에 대한 분기 데이터가 없습니다."

        out = pd.DataFrame(rows).sort_values("QuarterEnd").tail(years * 4)
        cols = ["QuarterEnd", "Price", "EPS", "PER", "ROE", "ROA", "NetIncome", "Equity", "Assets"]
        out = out[cols]
        return out.to_markdown(index=False)

    except Exception as e:
        return f"오류: {e}"



# Gemini API에 등록할 도구 목록
tools = [
    get_current_time,
    get_yf_stock_info,
    get_yf_stock_history,
    get_yf_recommendations,
    get_yf_tech_chart,      # ← 차트(base64) 반환
    get_yf_tech_values,     # ← 수치만 반환
    get_dart_indicators_quarterly,
]

# 실행 테스트
if __name__ == '__main__':
    # DART 기준 재무지표 (가격/ PER 제외)
    print(get_dart_indicators_quarterly("삼성전자", years=5, fs_div="CFS"))

    print("\n" + "="*50 + "\n")

    # DART + yfinance (PER 포함: 분기말 종가/분기 EPS)
    print(get_dart_indicators_quarterly("삼성전자", years=5, fs_div="CFS", ticker="005930.KS"))
