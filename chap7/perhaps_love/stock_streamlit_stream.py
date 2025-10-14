# === 탭 UI: 종합 대시보드 ===
import json
import streamlit as st

# 1) 필요한 함수 임포트
from gemini_functions import (
    get_yf_tech_chart,      # image_base64 + 지표 JSON 문자열 반환 :contentReference[oaicite:3]{index=3}
    get_yf_tech_values,     # 지표만 JSON 문자열 반환 :contentReference[oaicite:4]{index=4}
    get_dart_indicators_quarterly,  # 재무 테이블(마크다운) 반환 :contentReference[oaicite:5]{index=5}
)
from navernews import (
    search_latest_news_naver,             # 네이버 뉴스 원본 JSON 문자열 반환 :contentReference[oaicite:6]{index=6}
    summarize_news_and_sentiment_naver,   # 요약/감정 JSON 문자열 반환 :contentReference[oaicite:7]{index=7}
)

# (선택) 종합 리포트 에이전트가 있다면
try:
    from report_agent import generate_report
    _has_report_agent = True
except Exception:
    _has_report_agent = False


st.markdown("---")
st.header("📊 종합 대시보드")

# 공통 입력값
colA, colB, colC, colD = st.columns([1.2, 1, 1, 1])
with colA:
    _ticker = st.text_input("티커 (예: 005930.KS / AAPL)", value="005930.KS")
with colB:
    _corp = st.text_input("기업명 (DART/뉴스용)", value="삼성전자")
with colC:
    _period = st.selectbox("기간", ["3mo", "6mo", "1y", "2y"], index=1)
with colD:
    _news_days = st.slider("뉴스 최근 N일", min_value=1, max_value=30, value=7, step=1)

tab1, tab2, tab3, tab4 = st.tabs(["📈 차트", "📰 뉴스", "💰 재무지표", "📑 종합 리포트"])

# ========== 탭 1: 차트 ==========
with tab1:
    st.subheader("📈 기술적 차트")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("차트 그리기 (SMA/BB)", key="btn_chart"):
            try:
                # 차트(+지표) JSON 문자열 → dict 파싱
                resp = get_yf_tech_chart(ticker=_ticker, period=_period)
                payload = json.loads(resp)
                # 기존 유틸로 렌더 (이미지/수치) :contentReference[oaicite:8]{index=8}
                _render_payload(payload)  # image_base64 + 지표 카드
                with st.expander("원본 응답(JSON)"):
                    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
            except Exception as e:
                st.error(f"차트 오류: {e}")
    with col2:
        if st.button("지표만 보기 (차트 없음)", key="btn_values"):
            try:
                resp = get_yf_tech_values(ticker=_ticker, period=_period)
                payload = json.loads(resp)
                _render_payload(payload)  # 이미지 없으면 지표 카드만 렌더
                with st.expander("원본 응답(JSON)"):
                    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
            except Exception as e:
                st.error(f"지표 조회 오류: {e}")

# ========== 탭 2: 뉴스 ==========
with tab2:
    st.subheader("📰 최신 뉴스 & 감정 분석")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("네이버 뉴스 검색", key="btn_news_raw"):
            try:
                news_raw_json = search_latest_news_naver(
                    query=_corp or _ticker,
                    display=20,
                    sort="date",
                    recent_days=_news_days
                )  # JSON 문자열 반환 :contentReference[oaicite:9]{index=9}
                news_raw = json.loads(news_raw_json)
                st.success(f"가져온 기사: {len(news_raw.get('news', []))}건")
                with st.expander("원본 뉴스(JSON)"):
                    st.code(json.dumps(news_raw, ensure_ascii=False, indent=2), language="json")
            except Exception as e:
                st.error(f"뉴스 검색 오류: {e}")
    with c2:
        if st.button("요약 + 감정 분석", key="btn_news_sum"):
            try:
                # 바로 요약까지
                news_raw_json = search_latest_news_naver(
                    query=_corp or _ticker, display=20, sort="date", recent_days=_news_days
                )
                summarized_json = summarize_news_and_sentiment_naver(news_raw_json, max_sentences=3)  # :contentReference[oaicite:10]{index=10}
                payload = json.loads(summarized_json)

                st.caption(f"요약시각: {payload.get('summary_at','')}, 기사 수: {payload.get('count',0)}")
                items = payload.get("items", [])
                # 카드/아코디언 형태로 렌더
                for i, it in enumerate(items, 1):
                    title = it.get("title", "(제목 없음)")
                    with st.expander(f"{i}. {title}"):
                        st.write(f"**출처**: {it.get('source','-')} | **일시**: {it.get('date','-')}")
                        if it.get("link"):
                            st.write(f"[기사 링크]({it['link']})")
                        if it.get("snippet"):
                            st.write(f"> {it['snippet']}")
                        if it.get("summary"):
                            st.markdown("**요약**")
                            st.write(it["summary"])
                        if it.get("sentiment") is not None:
                            sc = it["sentiment"]
                            label = "긍정 😊" if sc > 0.2 else ("부정 😕" if sc < -0.2 else "중립 😐")
                            st.metric("감정 점수(-1~1)", f"{sc:+.2f}", label)

                with st.expander("원본 응답(JSON)"):
                    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")

            except Exception as e:
                st.error(f"요약/감정 오류: {e}")

# ========== 탭 3: 재무 ==========
with tab3:
    st.subheader("💰 재무 지표 (DART)")
    st.caption("분기 EPS/ROE/ROA/(선택)PER 등을 테이블로 보여줍니다.")
    use_per = st.checkbox("PER 포함(분기말 종가/분기 EPS)", value=True)
    if st.button("재무 테이블 가져오기", key="btn_fin"):
        try:
            # corp_name 필수. PER을 보려면 yfinance용 티커도 넘김
            md_table = get_dart_indicators_quarterly(
                corp_name=_corp or "",
                years=5,
                fs_div="CFS",
                ticker=_ticker if use_per else None
            )  # 마크다운 문자열 반환 :contentReference[oaicite:11]{index=11}
            st.markdown(md_table)
        except Exception as e:
            st.error(f"재무 조회 오류: {e}")

# ========== 탭 4: 종합 리포트 ==========
with tab4:
    st.subheader("📑 AI 종합 리포트")
    if not _has_report_agent:
        st.info("`report_agent.py`가 없거나 임포트 실패. 에이전트를 추가하면 한 페이지 리포트를 생성할 수 있어요.")
    else:
        if st.button("리포트 생성 🚀", key="btn_report"):
            try:
                res = generate_report(
                    ticker=_ticker.strip(),
                    corp_name=(_corp.strip() or None),
                    period=_period,
                    recent_days=_news_days
                )
                if res.report_md:
                    st.success("리포트 생성 완료!")
                    st.markdown(res.report_md)
                    st.download_button(
                        "리포트 저장 (Markdown)",
                        data=res.report_md.encode("utf-8"),
                        file_name=f"{_ticker}_AI_Report.md",
                        mime="text/markdown"
                    )
                else:
                    st.warning("리포트 생성에 실패했습니다.")
            except Exception as e:
                st.error(f"리포트 오류: {e}")
