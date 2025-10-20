# app_intent_driven.py
from __future__ import annotations
import os, re, json, traceback
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta

import streamlit as st
import pandas as pd
import google.generativeai as genai

# .env 로딩
try:
    from dotenv import load_dotenv, find_dotenv
    p = find_dotenv(usecwd=True)
    if p: load_dotenv(p, override=False)
except Exception: pass

# API 키 설정
DART_API_KEY = os.getenv("DART_API_KEY") or ""
NAVER_ID = os.getenv("NAVER_CLIENT_ID") or ""
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET") or ""
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or ""
if GOOGLE_API_KEY: genai.configure(api_key=GOOGLE_API_KEY)

# ---- 프로젝트 내 유틸 (기존 파일 활용) ----
from dart_functions import (
    get_dart_indicators_quarterly, normalize_financial_payload, add_growth_cols,
    apply_unit_format, get_ticker_from_name_fuzzy, BRAND_FIXES,
    get_historical_price, get_corp_outline
)
import navernews as newsmod
# --- Gemini 자동 함수 호출을 위한 도구 임포트 ---
import gemini_functions

st.set_page_config(page_title="K-주식 AI 챗봇", page_icon="📈", layout="wide")
st.title("📈 AI 주식 분석 챗봇")

# --- 1. 의도 분석 로직 (단순/복합 질문 구분) ---
PRICE_WORDS = ["주가", "시세", "종가", "가격", "얼마"]
NEWS_WORDS = ["뉴스", "기사", "소식", "이슈", "리포트", "공시"]
FIN_WORDS  = ["실적", "재무", "분기", "지표", "가치", "eps", "roe", "매출", "영업이익", "per"]
OUTLINE_WORDS = ["설명", "개요", "기업정보", "어떤 회사"]
FORECAST_WORDS = ["전망", "예측", "어때", "어떨까", "앞으로", "투자"]
KNOWN_CORP_ALIASES = sorted(list(BRAND_FIXES.keys()), key=len, reverse=True)

def parse_relative_date(query: str) -> Optional[date]:
    if "오늘" in query: return date.today()
    if "어제" in query: return date.today() - timedelta(days=1)
    return None

def parse_query_simple(query: str) -> Tuple[str, str, Optional[date]]:
    """단순하고 명확한 질문의 의도를 파악합니다. 복잡한 질문은 'complex_query'로 분류합니다."""
    lower_q = query.lower()
    
    # --- 안정성을 높인 새로운 다중 기업 인식 로직 ---
    found_subjects = []
    # 중복 인식을 방지하기 위해, 찾은 기업명을 임시로 마스킹
    temp_q = lower_q
    for alias in KNOWN_CORP_ALIASES:
        # 정규식으로 단어 경계를 확인하여 '삼성전자'가 '삼성전기'를 포함하지 않도록 함
        # re.IGNORECASE를 사용하여 대소문자 구분 없이 매칭
        for match in re.finditer(r'\b' + re.escape(alias) + r'\b', temp_q, re.IGNORECASE):
            original_term = query[match.start():match.end()]
            found_subjects.append(original_term)
            # 찾은 부분은 마스킹하여 중복 검색 방지
            temp_q = temp_q[:match.start()] + "[MASKED]" * len(alias) + temp_q[match.end():]

    # 두 개 이상의 기업이 언급되면 비교 등 복합 질문으로 처리
    if len(found_subjects) > 1:
        return query, "complex_query", None
        
    found_subject = found_subjects[0] if found_subjects else ""
    
    subject = found_subject if found_subject else query.strip()
    target_date = parse_relative_date(lower_q)
    
    if any(w in lower_q for w in FORECAST_WORDS):
        return query, "complex_query", None
    if any(w in lower_q for w in NEWS_WORDS):
        return subject, "news", None
    if any(w in lower_q for w in OUTLINE_WORDS):
        return subject, "outline", None
    if target_date or any(w in lower_q for w in PRICE_WORDS):
        return subject, "price_history", target_date or date.today()
    if any(w in lower_q for w in FIN_WORDS):
        return subject, "finance", None
    
    return query, "complex_query", None

# --- 2. 답변 생성 함수들 ---
def answer_complex_query(query: str) -> str:
    """Gemini의 자동 함수 호출 기능을 사용하여 복합적인 질문에 답변합니다."""
    if not GOOGLE_API_KEY: return "❌ GOOGLE_API_KEY가 설정되지 않아 AI 분석을 할 수 없어요."
    st.info("AI가 질문을 분석하고, 필요한 도구를 사용하여 종합적인 답변을 생성하고 있습니다...")

    try:
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=gemini_functions.tools
        )
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(query)
        return response.text
    except Exception as e:
        return f"❌ AI 분석 중 오류가 발생했습니다: {str(e)}"

def answer_outline(subject: str) -> str:
    corp_info = get_ticker_from_name_fuzzy(subject)
    if not corp_info.get("best"): return f"❌ '{subject}' 기업을 찾을 수 없습니다."
    best_match = corp_info["best"]
    outline_data = get_corp_outline(best_match["corp_code"])
    if outline_data.get("status") != "000": return f"❌ 기업 개황 정보 조회 실패: {outline_data.get('message')}"
    hm_url = outline_data.get('hm_url')
    hm_link = f"[{hm_url}]({hm_url})" if hm_url and hm_url.startswith('http') else "정보 없음"
    response_lines = [f"### 🏢 {outline_data.get('corp_name', '')}", "---", f"- **대표자**: {outline_data.get('ceo_nm', '정보 없음')}", f"- **설립일**: {outline_data.get('est_dt', '정보 없음')}", f"- **주소**: {outline_data.get('adres', '정보 없음')}", f"- **홈페이지**: {hm_link}", f"- **주요사업**: {outline_data.get('main_bsns_nm', '정보 없음')}"]
    return "\n".join(response_lines)

def answer_price_history(subject: str, target_date: date) -> str:
    corp_info = get_ticker_from_name_fuzzy(subject)
    if not corp_info.get("best"): return f"❌ '{subject}' 기업을 찾을 수 없습니다."
    best_match, corp_name, stock_code = corp_info["best"], corp_info["best"]["corp_name"], corp_info["best"]["stock_code"]
    if not stock_code or not stock_code.strip(): return f"❌ '{corp_name}'은(는) 상장사가 아닙니다."
    ticker = f"{stock_code}.KS"
    result = get_historical_price(ticker, target_date)
    if result.get("error"):
        ticker_kq = ticker.replace(".KS", ".KQ")
        result = get_historical_price(ticker_kq, target_date)
    if result.get("error"): return f"❌ '{corp_name}' 주가 조회 오류: {result['error']}"
    price_date, close_price = result['date'], result['close']
    return f"**{price_date}** 기준 **{corp_name}**의 종가는 **{close_price:,.0f}원**입니다."

def answer_finance(subject: str, years: int = 2) -> Tuple[str, Optional[pd.DataFrame]]:
    corp_info = get_ticker_from_name_fuzzy(subject)
    if not corp_info.get("best"): return f"❌ '{subject}' 기업을 찾을 수 없습니다.", None
    payload = get_dart_indicators_quarterly(corp_name=corp_info["best"]["corp_name"], symbol=corp_info["best"]["stock_code"], years=years)
    if payload.get("error"): return f"❌ 재무 조회 실패: {payload.get('error')}", None
    meta, df_raw = normalize_financial_payload(payload)
    if df_raw.empty: return "데이터가 비어 있습니다.", None
    df_growth = add_growth_cols(df_raw)
    latest4 = df_growth.head(4).to_dict(orient="records")
    bullets = []
    for r in latest4:
        qlab = f"{int(r['연도'])}년 {r['분기']}" if pd.notna(r.get('연도')) else "최신 분기"
        s = [f"{lab} {val:,.2f}억원" for col, lab in [("매출","매출"), ("영업이익","영업이익")] if (val:=r.get(col)) is not None and pd.notna(val)]
        try: s += [f"{lab} {f_str.format(v=r[col])}" for col, lab, f_str in [("EPS","EPS","{v:,.0f}원"), ("PER","PER","{v:.2f}배"), ("ROE(%)","ROE","{v:.2f}%")] if r.get(col) is not None and pd.notna(r.get(col))]
        except (ValueError, TypeError): pass
        bullets.append(f"- **{qlab}**: " + (", ".join(s) if s else "(수치 없음)"))
    header = f"**{meta.corp_name}** (코드: {meta.stock_code}) · {years}년"
    return header + "\n\n" + "\n".join(bullets), apply_unit_format(df_growth)

def answer_news(subject: str, limit: int = 8) -> Tuple[str, List[Dict[str, Any]]]:
    payload = newsmod.search_latest_news_naver(query=subject, display=max(30, limit), sort="date", recent_days=30, return_meta=True)
    if payload.get("error"): return f"❌ 뉴스 API 오류: {payload.get('error')}", []
    items = payload.get("items", [])
    if not items: return f"'{subject}' 관련 최신 뉴스가 없습니다.", []
    summarized = newsmod.summarize_news_and_sentiment_naver({"items": items})
    with_topics = newsmod.classify_news_topics_naver(summarized)
    shown = with_topics.get("items", [])[:limit]
    title = f"📰 **뉴스 요약 — '{subject}'** (결과: {len(shown)}건)"
    return title, shown

# --------- 3. 메인 UI 로직 ---------
if "chat" not in st.session_state:
    st.session_state.chat: List[Dict[str, Any]] = [{"role": "assistant", "content": "안녕하세요! AI 주식 분석 챗봇입니다. 무엇이 궁금하신가요?"}]

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if isinstance(msg.get("df"), pd.DataFrame) and not msg.get("df").empty:
            with st.expander("상세 표 보기"): st.dataframe(msg["df"], use_container_width=True, hide_index=True)
        if msg.get("news"):
            with st.expander("뉴스 목록 보기"):
                for it in msg["news"]:
                    link, date_str = it.get("originallink") or it.get("link") or "#", it.get("pubDateKST", "")
                    try: date_iso = pd.to_datetime(date_str).strftime('%Y-%m-%d %H:%M') if date_str else it.get("pubDate", "")
                    except pd.errors.ParserError: date_iso = it.get("pubDate", "")
                    st.markdown(f"- [{it.get('title','(제목 없음)')}]({link}) ({date_iso})")

user_q = st.chat_input("예: '삼성전자 실적', '카카오 어제 주가', 'HBM 관련 뉴스 10개', '현대차와 기아차 실적 비교'")
if user_q:
    st.session_state.chat.append({"role": "user", "content": user_q})
    
    subject, intent, target_date = parse_query_simple(user_q)
    
    with st.chat_message("assistant"):
        with st.spinner(f"'{subject}'({intent}) 분석 중... 🚀"):
            try:
                if intent == "complex_query":
                    response_text = answer_complex_query(user_q)
                    st.session_state.chat.append({"role": "assistant", "content": response_text})
                elif intent == "outline":
                    response_text = answer_outline(subject)
                    st.session_state.chat.append({"role": "assistant", "content": response_text})
                elif intent == "price_history" and target_date:
                    response_text = answer_price_history(subject, target_date)
                    st.session_state.chat.append({"role": "assistant", "content": response_text})
                elif intent == "news":
                    limit = int(re.search(r'(\d+)\s*개', user_q).group(1)) if re.search(r'(\d+)\s*개', user_q) else 5
                    response_text, items = answer_news(user_q, limit=limit)
                    st.session_state.chat.append({"role": "assistant", "content": response_text, "news": items})
                else: # finance
                    years = int(re.search(r"(\d+) ?년", user_q).group(1)) if re.search(r"(\d+) ?년", user_q) else 2
                    body, df_show = answer_finance(subject, years=years)
                    st.session_state.chat.append({"role": "assistant", "content": body, "df": df_show})
            except Exception:
                error_msg = f"❌ 처리 중 오류가 발생했습니다.\n```\n{traceback.format_exc()}\n```"
                st.session_state.chat.append({"role": "assistant", "content": error_msg})
    st.rerun()