# app_intent_driven.py
from __future__ import annotations
import os, re, json, traceback
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import pandas as pd

# .env 로딩(있으면)
try:
    from dotenv import load_dotenv, find_dotenv
    p = find_dotenv(usecwd=True)
    if p: load_dotenv(p, override=False)
except Exception:
    pass

DART_API_KEY = os.getenv("DART_API_KEY") or os.getenv("OPEN_DART_API_KEY") or ""
NAVER_ID = os.getenv("NAVER_CLIENT_ID") or ""
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET") or ""

# ---- 프로젝트 내 유틸 (기존 파일 활용) ----
from dart_functions import (
    get_dart_indicators_quarterly,
    normalize_financial_payload,
    add_growth_cols,
    apply_unit_format,
)

import navernews as newsmod  # ← 위에서 교체한 파일

st.set_page_config(page_title="K-주식 챗봇 (대화형)", page_icon="🤖", layout="wide")
st.title("🤖 주식 챗봇 연구 — 질문만 하세요!")

NEWS_WORDS = ["뉴스", "기사", "헤드라인", "속보", "보도", "리포트", "증권사", "이슈"]
FIN_WORDS  = ["실적", "재무", "분기", "EPS", "ROE", "ROA", "매출", "영업이익", "순이익", "재무지표", "가이던스"]

def detect_intent(q: str) -> str:
    t = q.lower()
    if any(w.lower() in t for w in NEWS_WORDS): return "news"
    if any(w.lower() in t for w in FIN_WORDS):  return "finance"
    # 기본 파이낸스 우선
    return "finance"

# -------- 파이낸스(대화형 요약) --------
def answer_finance(user_text: str, years: int = 2, fs_div: str = "CFS", unit: str = "억원") -> Tuple[str, Optional[pd.DataFrame]]:
    if not DART_API_KEY:
        return "❌ DART_API_KEY가 설정되어 있지 않아 재무지표를 불러올 수 없어요.", None

    payload = get_dart_indicators_quarterly(corp_name=user_text, years=years, fs_div=fs_div)
    if payload.get("error"):
        return f"❌ 재무지표 조회 실패: {payload.get('error')}", None

    meta, df_raw = normalize_financial_payload(payload)
    if df_raw.empty:
        return "데이터가 비어 있어요. 기업명이 맞는지 확인해 주세요.", None

    df_growth = add_growth_cols(df_raw, cols=["매출", "영업이익", "순이익"])

    latest4 = df_growth.head(4).to_dict(orient="records")
    corp = payload.get("corp", {})
    corp_name = corp.get("corp_name", "기업")
    stock_code= corp.get("stock_code", "-")

    def fmt_unit(v):
        try:
            v = float(v)
        except Exception:
            return "N/A"
        if unit == "억원":
            return f"{v/1e8:,.2f}억원"
        if unit == "조원":
            return f"{v/1e12:,.3f}조원"
        return f"{v:,.0f}원"

    bullets = []
    for r in latest4:
        qlab = f"{int(r['연도'])}년 {r['분기']}"
        s = []
        for col, lab in [("매출","매출"),("영업이익","영업이익"),("순이익","순이익")]:
            if r.get(col) is not None and pd.notna(r.get(col)):
                s.append(f"{lab} {fmt_unit(r[col])}")
        if r.get("EPS") not in (None, "nan") and pd.notna(r.get("EPS")):
            s.append(f"EPS {int(r['EPS']):,}원")
        for col, lab in [("매출_QoQ(%)","매출 QoQ"),("매출_YoY(%)","매출 YoY"),
                         ("영업이익_QoQ(%)","영업이익 QoQ"),("영업이익_YoY(%)","영업이익 YoY")]:
            val = r.get(col)
            if val is not None and pd.notna(val):
                s.append(f"{lab} {val:+.1f}%")
        bullets.append(f"- {qlab}: " + (", ".join(s) if s else "(수치 없음)"))

    df_show = apply_unit_format(df_growth, unit=unit)
    header = f"**{corp_name}** (코드 {stock_code}) · {years}년치 · {'연결' if fs_div=='CFS' else '별도'} · 단위:{unit}"
    body = header + "\n\n" + "\n".join(bullets)
    return body, df_show

# -------- 뉴스(요약/감정/토픽) --------
# (기존 파일의 answer_news 함수 자리에 교체)
def answer_news(keyword: str, limit: int = 8) -> Tuple[str, List[Dict[str, Any]]]:
    NAVER_ID = os.getenv("NAVER_CLIENT_ID") or ""
    NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET") or ""
    if not (NAVER_ID and NAVER_SECRET):
        return "❌ NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 없어 뉴스 검색이 불가합니다.", []

    # meta 포함으로 호출 → 어떤 쿼리로 찾았는지 UI에 함께 보여줌
    payload = newsmod.search_latest_news_naver(
        query=keyword,
        display=max(30, limit),
        sort="date",
        recent_days=7,
        return_meta=True,
    )
    if isinstance(payload, dict) and payload.get("error"):
        return f"❌ 네이버 뉴스 API 오류: {payload.get('error')}", []

    items = payload.get("items", [])
    tried = payload.get("meta", {}).get("tried", [])
    if not items:
        # 마지막 안전장치: 핵심토큰 직접 재호출
        base = newsmod._best_token(keyword)  # 공개 함수로 써도 무방
        payload2 = newsmod.search_latest_news_naver(
            query=base, display=100, sort="date", recent_days=14, return_meta=True
        )
        if not payload2.get("error"):
            items = payload2.get("items", [])
            tried += payload2.get("meta", {}).get("tried", [])

    if not items:
        used_text = ", ".join([f"{t['q']}({t['sort']})" for t in tried]) or keyword
        return f"'{keyword}' 관련 기사가 없습니다. (시도: {used_text})", []

    summarized = newsmod.summarize_news_and_sentiment_naver({"items": items})
    with_topics = newsmod.classify_news_topics_naver(summarized)

    shown = with_topics.get("items", [])[:limit]
    used_text = ", ".join([f"{t['q']}({t['sort']})" for t in tried])
    title = f"📰 **뉴스 요약 — '{keyword}'** · 사용쿼리: {used_text} · 표시 {len(shown)}건 / 수집 {len(items)}건"
    lines = [f"- {it.get('title','(제목 없음)')} · 감정:{it.get('sentiment','중립')} · 토픽:{it.get('topic','기타')}" for it in shown]
    return title + "\n" + "\n".join(lines), shown


# --------- UI ---------
if "chat" not in st.session_state:
    st.session_state.chat: List[Dict[str, Any]] = [
        {"role": "assistant", "content": "무엇이 궁금하세요? 예) '삼성전기 최근 분기 실적 요약', '삼성전자 최신 뉴스 보여줘'"},
    ]

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if isinstance(msg.get("df"), pd.DataFrame) and not msg["df"].empty:
            with st.expander("표로 보기", expanded=False):
                st.dataframe(msg["df"], use_container_width=True, hide_index=True)
        if msg.get("news"):
            with st.expander("뉴스 목록 펼치기", expanded=True):
                for it in msg["news"]:
                    link = it.get("originallink") or it.get("link") or "#"
                    date = it.get("pubDateKST") or it.get("pubDate", "")
                    st.markdown(f"- [{it.get('title','(제목 없음)')}]({link}) · {date}")
                    if it.get("summary"):
                        st.caption("요약: " + it["summary"])

user_q = st.chat_input("자연어로 물어보세요. (예: '현대차 2년치 분기 실적 요약', '삼성전자 최신 뉴스 보여줘')")
if user_q:
    intent = detect_intent(user_q)
    try:
        if intent == "news":
            title, items = answer_news(user_q, limit=8)
            st.session_state.chat.append({"role": "user", "content": user_q})
            st.session_state.chat.append({"role": "assistant", "content": title, "news": items})
        else:
            years = int(re.search(r"(\d+) ?년", user_q).group(1)) if re.search(r"(\d+) ?년", user_q) else 2
            fs_div = "OFS" if ("별도" in user_q) else "CFS"
            unit = "조원" if ("조원" in user_q) else ("원" if ("원" in user_q and "억원" not in user_q) else "억원")
            body, df_show = answer_finance(user_q, years=years, fs_div=fs_div, unit=unit)
            st.session_state.chat.append({"role": "user", "content": user_q})
            st.session_state.chat.append({"role": "assistant", "content": body, "df": df_show})
    except Exception:
        st.session_state.chat.append({"role":"assistant","content":"❌ 처리 중 오류가 발생했어요.\n```\n"+traceback.format_exc()+"\n```"})
    st.rerun()
