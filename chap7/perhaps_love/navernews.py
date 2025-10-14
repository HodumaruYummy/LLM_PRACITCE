# navernews.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, html, json, hashlib
import datetime as dt
from typing import Any, Dict, List, Optional

import requests

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
KST = dt.timezone(dt.timedelta(hours=9), name="KST")

# ===== 공통 =====
STOPWORDS = {"최신","뉴스","보여줘","알려줘","기사","헤드라인","이슈","검색","관련","최근"}
TAG_RE = re.compile(r"<[^>]+>")

def _clean_html(s: str) -> str:
    if not s: return ""
    s = html.unescape(s)
    s = TAG_RE.sub("", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def _parse_pubdate(s: str) -> Optional[dt.datetime]:
    if not s: return None
    fmts = ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S +0900",
            "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]
    for f in fmts:
        try:
            d = dt.datetime.strptime(s, f)
            if not d.tzinfo: d = d.replace(tzinfo=KST)
            return d.astimezone(KST)
        except Exception: pass
    return None

def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for it in items:
        t = _clean_html(it.get("title",""))
        link = it.get("originallink") or it.get("link") or ""
        key = hashlib.md5((t+"|"+link).encode("utf-8")).hexdigest()
        if key in seen: continue
        seen.add(key); out.append(it)
    return out

def _looks_like_ad(title: str, desc: str) -> bool:
    txt = (title+" "+desc).lower()
    return any(w in txt for w in ["sponsored","광고","쿠폰","특가","할인 코드","제휴","쇼핑"])

def _normalize_query(q: str) -> str:
    q = (q or "").strip()
    # 불용어 제거
    for w in STOPWORDS: q = q.replace(w, " ")
    q = re.sub(r"[“”\"'()\[\]]+", " ", q)
    q = re.sub(r"\s{2,}", " ", q).strip()
    return q

def _best_token(q: str) -> str:
    """
    문장에서 한글/영문/숫자 토큰만 추출 → 불용어 제거 → 가장 긴 토큰/구를 돌려줌.
    예) '삼성전자 최신 뉴스 보여줘' → '삼성전자'
    """
    q = _normalize_query(q)
    # 한글/영문/숫자와 공백만 남기고 정리
    q = re.sub(r"[^0-9A-Za-z가-힣\s]", " ", q)
    tokens = [t for t in q.split() if t and t not in STOPWORDS]
    if not tokens: return q or ""
    # 가장 긴 토큰 우선, 단 두 단어까지 결합 시도
    tokens.sort(key=len, reverse=True)
    if len(tokens) >= 2:
        # '기업명 키워드' 형태가 남았으면 그대로(예: '삼성전자 반도체')
        two = f"{tokens[0]} {tokens[1]}".strip()
        return two if len(two) <= 30 else tokens[0]
    return tokens[0]

# ===== API =====
def search_latest_news_naver(
    query: str,
    display: int = 20,
    sort: str = "date",
    recent_days: int = 7,
    dedupe: bool = True,
    fallback: bool = True,
    timeout: int = 10,
    return_meta: bool = False,
) -> Dict[str, Any]:
    """
    네이버 뉴스 API(최신순 기본) — 강력한 fallback 내장.
    - query: 자연어 그대로 입력 가능
    - recent_days: 최근 N일 필터(최종 절박 재시도에서는 해제)
    - return_meta: 디버깅용으로 사용 쿼리/호출횟수 반환
    """
    cid = os.getenv("NAVER_CLIENT_ID")
    csec = os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        return {"error": "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 미설정"}

    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    used = []  # 어떤 쿼리를 썼는지 기록

    def _call(q: str, srt: str, disp: int) -> Dict[str, Any]:
        used.append({"q": q, "sort": srt, "display": disp})
        resp = requests.get(
            NAVER_NEWS_URL,
            headers=headers,
            params={"query": q, "display": max(1, min(disp, 100)), "sort": srt},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {"error": f"Naver API 오류: {resp.status_code} {resp.text}"}
        return resp.json()

    # 1차: 원문
    data = _call(query.strip(), sort, display)
    if isinstance(data, dict) and data.get("error"):
        return data
    items = data.get("items", []) if isinstance(data, dict) else []

    # 2차: 정제쿼리
    if fallback and len(items) < 3:
        q2 = _normalize_query(query)
        if q2:
            data2 = _call(q2, sort, max(display, 50))
            if not data2.get("error"):
                items = data2.get("items", []) or items

    # 3차: 핵심토큰 + 유사도 정렬
    if fallback and len(items) < 3:
        q3 = _best_token(query)
        if q3:
            data3 = _call(q3, "sim", 100)
            if not data3.get("error"):
                items = data3.get("items", []) or items

    # 4차: 핵심토큰 + 최신순 + 최근일 필터 해제(마지막 시도)
    last_try = False
    if fallback and len(items) < 3:
        q4 = _best_token(query)
        if q4:
            last_try = True
            data4 = _call(q4, "date", 100)
            if not data4.get("error"):
                items = data4.get("items", []) or items

    # 정리(HTML/광고/중복/날짜)
    cleaned: List[Dict[str, Any]] = []
    cutoff = dt.datetime.now(KST) - dt.timedelta(days=recent_days)
    for it in items:
        title = _clean_html(it.get("title",""))
        desc  = _clean_html(it.get("description",""))
        if _looks_like_ad(title, desc): continue
        pub = _parse_pubdate(it.get("pubDate",""))
        # 마지막 시도에서는 날짜 필터 해제, 그 외에는 최근 N일만
        if not last_try and pub and pub < cutoff: continue
        new = dict(it); new["title"]=title; new["description"]=desc
        new["pubDateKST"] = pub.isoformat() if pub else ""
        cleaned.append(new)

    if dedupe: cleaned = _dedupe(cleaned)

    if return_meta:
        return {"items": cleaned, "meta": {"tried": used, "count": len(cleaned)}}
    return {"items": cleaned}

# ===== 간단 요약/감정/토픽 =====
_POS = ["호조","상승","확대","선정","수주","개선","돌파","최고","신기록","긍정","호재","강세"]
_NEG = ["부진","하락","감소","적자","실패","리콜","논란","경고","악재","약세","감산"]

def _sentiment_score(text: str) -> float:
    t = text.lower()
    sc = 0.0
    for w in _POS:
        if w in t: sc += 1
    for w in _NEG:
        if w in t: sc -= 1
    return sc

def _first_sentence(title: str, desc: str) -> str:
    import re as _re
    sents = _re.split(r"[.。?!]\s+", desc)
    first = (sents[0].strip() if sents and sents[0] else "") or title
    return (first[:160] + "…") if len(first) > 160 else first

def summarize_news_and_sentiment_naver(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = {"items": []}
    for it in payload.get("items", []):
        title = it.get("title",""); desc = it.get("description","")
        sumy = _first_sentence(title, desc)
        sc = _sentiment_score(title + " " + desc)
        sent = "긍정" if sc > 0.3 else ("부정" if sc < -0.3 else "중립")
        ni = dict(it); ni.update({"summary": sumy, "sentiment": sent, "score": sc})
        out["items"].append(ni)
    return out

_TOPIC_RULES = [
    ("실적/가이던스", ["실적","잠정","컨센서스","가이던스","영업이익","매출","순이익","실적발표"]),
    ("제품/기술",     ["출시","공개","신제품","라인업","칩","반도체","스마트폰","AI","HBM","메모리"]),
    ("투자/설비",     ["증설","라인","공장","투자","CAPEX","설비","파운드리"]),
    ("주가/증권",     ["목표가","리포트","증권사","투자의견","상향","하향","강세","약세"]),
    ("규제/분쟁",     ["규제","제재","소송","분쟁","조사","벌금","리콜"]),
    ("기타",          []),
]
def classify_news_topics_naver(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = {"items": []}
    for it in payload.get("items", []):
        txt = (it.get("title","") + " " + it.get("description",""))
        cat = "기타"
        for label, kws in _TOPIC_RULES:
            if kws and any(k in txt for k in kws): cat = label; break
        ni = dict(it); ni["topic"] = cat; out["items"].append(ni)
    return out
