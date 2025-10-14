# streamlit.py
# 메인: 챗봇 / 사이드바: 재무지표 검색 + 뉴스 검색 (키는 .env에서 자동 로드)
from __future__ import annotations

import os, json, traceback
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import google.generativeai as genai

# --- .env 자동 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- 로컬 데이터 유틸 (당신이 제공한 dart_functions.py 사용)
from dart_functions import (
    get_dart_indicators_quarterly,
    normalize_financial_payload,
    add_growth_cols,
    apply_unit_format,
    CorpMeta,
)

# --- (있으면 사용) 네이버 뉴스 헬퍼
try:
    import navernews as newsmod
    HAS_NEWS = True
except Exception:
    newsmod, HAS_NEWS = None, False

# =========================
# 전역 설정
# =========================
st.set_page_config(page_title="K-주식 챗봇", page_icon="🤖", layout="wide")

# --- 환경변수 키 읽기
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
DART_API_KEY = os.getenv("DART_API_KEY", "") or os.getenv("OPEN_DART_API_KEY", "")

# Gemini 설정(키가 있으면 자동 활성화)
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# =========================
# 사이드바: 상태/검색 UI
# =========================
with st.sidebar:
    st.title("🔎 사이드바")

    # 키 상태 표시
    st.subheader("🔐 키 상태")
    st.write(f"- Google: {'✅ 설정됨' if GOOGLE_API_KEY else '❌ 없음'}")
    st.write(f"- DART: {'✅ 설정됨' if DART_API_KEY else '❌ 없음'}")
    if not DART_API_KEY:
        st.caption("※ .env에 DART_API_KEY(또는 OPEN_DART_API_KEY)를 추가하세요.")
    if not GOOGLE_API_KEY:
        st.caption("※ .env에 GOOGLE_API_KEY를 추가하면 요약/대화가 활성화됩니다.")

    st.markdown("---")
    st.subheader("📊 재무지표 검색 (DART)")
    corp_query = st.text_input("기업명 또는 종목코드(6자리)", value="삼성전기")
    years = st.slider("조회 연수(과거 N년)", min_value=1, max_value=5, value=2)
    fs_div = st.selectbox("연결/별도", ["CFS", "OFS"], index=0)
    unit = st.radio("표시 단위", ["억원", "조원", "원"], horizontal=True, index=0)
    add_growth_opt = st.checkbox("QoQ/YoY 증감률 포함", value=True)
    btn_fin = st.button("📡 재무지표 불러와서 챗에 추가")

    st.markdown("---")
    st.subheader("📰 뉴스 검색")
    news_query = st.text_input("검색어", value=corp_query or "삼성전자")
    news_limit = st.slider("표시 건수", min_value=3, max_value=20, value=8)
    btn_news = st.button("📰 뉴스 검색해서 챗에 추가")

# =========================
# 세션 스토어: 대화/상태
# =========================
if "chat" not in st.session_state:
    st.session_state.chat: List[Dict[str, Any]] = [
        {"role": "assistant", "content": "안녕하세요! 사이드바에서 재무지표/뉴스를 챗에 추가해 보세요. 어떤 분석이든 도와드릴게요 😊"}
    ]

def _append_message(role: str, content: str, df: Optional[pd.DataFrame] = None, meta: Optional[Dict[str,str]] = None, news: Optional[List[Dict[str,Any]]] = None):
    st.session_state.chat.append({
        "role": role,
        "content": content,
        "df": df,
        "meta": meta or {},
        "news": news or [],
    })

# =========================
# 사이드바 액션: 재무지표 검색
# =========================
def handle_financial_search():
    if not DART_API_KEY:
        _append_message("assistant", "❌ DART_API_KEY가 설정되어 있지 않아 조회할 수 없어요.\n.env에 `DART_API_KEY=...` (또는 `OPEN_DART_API_KEY=...`)를 추가해 주세요.")
        return
    try:
        q = (corp_query or "").strip()
        if not q:
            _append_message("assistant", "기업명/종목코드를 입력해 주세요.")
            return

        # 1) DART API 조회
        if q.isdigit() and len(q) == 6:
            payload = get_dart_indicators_quarterly(symbol=q, years=years, fs_div=fs_div)
        else:
            payload = get_dart_indicators_quarterly(corp_name=q, years=years, fs_div=fs_div)

        if "error" in payload:
            _append_message("assistant", f"❌ DART 조회 실패: {payload['error']}")
            return

        # 2) 정규화 → 표 생성
        meta, df_raw = normalize_financial_payload(payload)
        df_work = df_raw.copy()
        if add_growth_opt and not df_work.empty:
            df_work = add_growth_cols(df_work, cols=["매출", "영업이익", "순이익"])
        df_show = apply_unit_format(df_work, unit=unit)

        # 3) 요약 코멘트(Gemini)
        comment = ""
        if GOOGLE_API_KEY:
            try:
                model = genai.GenerativeModel("gemini-2.5-flash")
                latest = df_raw.iloc[0].to_dict() if not df_raw.empty else {}
                corp_name = meta.corp_name if isinstance(meta, CorpMeta) else meta.get("corp_name", "-")
                stock_code = meta.stock_code if isinstance(meta, CorpMeta) else meta.get("stock_code", "-")
                prompt = f"""
당신은 한국어를 사용하는 증권 애널리스트입니다.
다음 기업의 최근 분기 재무 데이터를 보고 6~8줄의 간결한 코멘트를 작성하세요.
- 톤: 중립/설명형
- 숫자: {unit} 단위로 자연스럽게
- 가능하면 QoQ/YoY 관찰 1~2줄 포함
- 결측 데이터가 있다면 언급
기업: {corp_name} (종목코드 {stock_code})
최신행(원본수치): {latest}
표 전체(원본수치 JSON): {df_raw.to_json(orient="records", force_ascii=False)}
현재 표시는 단위({unit}) / 증감률 포함({add_growth_opt})
"""
                resp = model.generate_content(prompt)
                comment = (resp.text or "").strip()
            except Exception:
                comment = "⚠️ Gemini 요약 생성 중 오류가 발생했어요."
        else:
            comment = "💡 .env에 GOOGLE_API_KEY가 없어서 요약은 생략했어요."

        # 4) 챗에 추가
        corp_name = meta.corp_name if isinstance(meta, CorpMeta) else meta.get("corp_name", "-")
        stock_code = meta.stock_code if isinstance(meta, CorpMeta) else meta.get("stock_code", "-")
        header = f"**{corp_name}** (종목코드 {stock_code}) · 단위: {unit} · 연결구분: {fs_div} · 조회연수: {years}년"
        _append_message("assistant", f"{header}\n\n{comment}", df=df_show, meta={"corp_name": corp_name, "stock_code": stock_code})

    except Exception:
        _append_message("assistant", "❌ 재무지표 처리 중 오류가 발생했어요.\n```\n" + traceback.format_exc() + "\n```")

# =========================
# 사이드바 액션: 뉴스 검색
# =========================
def handle_news_search():
    try:
        if newsmod is None:
            _append_message("assistant", "⚠️ navernews 모듈 import 실패로 뉴스 검색을 건너뜁니다.")
            return

        # ✅ 지원하는 함수 자동 탐지
        search_func = None
        if hasattr(newsmod, "search_latest_news"):
            search_func = newsmod.search_latest_news
        elif hasattr(newsmod, "search_latest_news_naver"):
            search_func = newsmod.search_latest_news_naver

        if search_func is None:
            _append_message("assistant", "⚠️ navernews.py 안에 search_latest_news(또는 search_latest_news_naver)가 없어 뉴스 검색을 건너뜁니다.")
            return

        q = (news_query or "").strip()
        if not q:
            _append_message("assistant", "검색어를 입력해 주세요.")
            return

        # ✅ 시그니처 차이 대응
        try:
            # search_latest_news(query, max_items=?, recent_days=?, sort=?)
            payload = search_func(keyword=q, max_items=int(news_limit), recent_days=7, sort="date")
        except TypeError:
            # search_latest_news_naver(query, display=?, sort=?, recent_days=?)
            payload = search_func(query=q, display=int(news_limit), sort="date", recent_days=7)

        if isinstance(payload, dict) and payload.get("error"):
            # 보통 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 미설정일 때
            _append_message("assistant", f"❌ 네이버 뉴스 API 오류: {payload.get('error')}")
            return

        # dict or str(JSON) 모두 처리
        if not isinstance(payload, dict):
            import json as _json
            payload = _json.loads(payload)

        items = payload.get("items", [])[: int(news_limit)]
        if not items:
            _append_message("assistant", f"'{q}' 관련 뉴스가 없었습니다.")
            return

        _append_message("assistant", f"📰 **뉴스 결과** — '{q}' 상위 {len(items)}건을 가져왔어요.", news=items)

    except Exception:
        _append_message("assistant", "❌ 뉴스 검색 중 오류가 발생했어요.\n```\n" + traceback.format_exc() + "\n```")


# =========================
# 버튼 동작
# =========================
if btn_fin:
    handle_financial_search()
if btn_news:
    handle_news_search()

# =========================
# 메인: 챗봇 UI
# =========================
st.title("🤖 주식 챗봇 연구")

# 기존 메시지 렌더링
for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if isinstance(msg.get("df"), pd.DataFrame) and not msg["df"].empty:
            st.dataframe(msg["df"], use_container_width=True, hide_index=True)
        if msg.get("news"):
            with st.expander("뉴스 목록 펼치기", expanded=True):
                for it in msg["news"]:
                    title = it.get("title", "(제목 없음)")
                    link = it.get("link", "#")
                    date = it.get("date", "")
                    st.markdown(f"- [{title}]({link}) · {date}")

# 사용자 입력 → 일반 대화
user_text = st.chat_input("메시지를 입력하세요. (예: '삼성전기 최근 실적 요약해줘')")
if user_text:
    st.session_state.chat.append({"role": "user", "content": user_text})

    reply = "💡 .env에 GOOGLE_API_KEY가 없어 일반 대화를 생략했어요."
    if GOOGLE_API_KEY:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            sys_hint = """
당신은 한국 주식 도우미 챗봇입니다.
- 사이드바의 '재무지표 검색'과 '뉴스 검색' 기능을 적절히 제안하세요.
- 숫자와 금융 용어는 한국어 기준으로 설명하세요.
"""
            history_text = "\n\n".join(
                [f"{m['role']}: {m['content']}" for m in st.session_state.chat[-10:] if isinstance(m.get("content"), str)]
            )
            prompt = f"{sys_hint}\n\n대화 기록(일부):\n{history_text}\n\n사용자 최신 입력:\n{user_text}\n\n자연스럽고 간결하게 답변하세요."
            resp = model.generate_content(prompt)
            reply = (resp.text or "").strip()
        except Exception:
            reply = "⚠️ 답변 생성 중 오류가 발생했어요."

    st.session_state.chat.append({"role": "assistant", "content": reply})
    st.rerun()
