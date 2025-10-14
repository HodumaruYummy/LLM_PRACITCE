# --- FAST broker_reports.py ---
from __future__ import annotations
import os, re, json, time, requests, datetime as dt
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://finance.naver.com/research"

def _abs(href: str) -> str:
    if not href: return ""
    if href.startswith("http"): return href
    return "https://finance.naver.com" + href

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _parse_date(s: str) -> str:
    s = (s or "").strip()
    m = re.search(r"20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}", s)
    if m:
        t = m.group(0).replace("/", ".").replace("-", ".")
        y, mth, d = [p.zfill(2) for p in t.split(".")[:3]]
        return f"{y}.{mth}.{d}"
    return s

def _session(timeout: float = 10.0) -> tuple[requests.Session, float]:
    s = requests.Session()
    retry = Retry(total=3, read=3, connect=3, backoff_factor=0.3,
                  status_forcelist=(429,500,502,503,504), allowed_methods=frozenset(["GET"]))
    ad = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=32)
    s.mount("http://", ad); s.mount("https://", ad)
    return s, timeout

def _fetch_html(sess: requests.Session, url: str, timeout: float) -> str | None:
    try:
        r = sess.get(url, headers=HDRS, timeout=timeout)
        r.raise_for_status(); return r.text
    except Exception:
        return None

def _extract_snippet(html: str, limit: int = 800) -> str:
    if not html: return ""
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for sel in ["div.scr01", "div#content", "div.articleCont", "div#contentarea"]:
        box = soup.select_one(sel)
        if box: candidates.append(box.get_text(" "))
    txt = _clean(" ".join(candidates) or soup.get_text(" "))
    return txt[:limit]

def _keep_by_date(date: str, cutoff: dt.datetime) -> bool:
    try:
        d = dt.datetime.strptime(date.replace(".", "-"), "%Y-%m-%d")
        return d >= cutoff
    except Exception:
        return True

def _match_query(title: str, snippet: str, query: str | None) -> bool:
    if not query: return True
    q = query.strip().lower()
    if not q: return True
    return (q in (title or "").lower()) or (q in (snippet or "").lower())

def search_broker_reports_naver(
    query: str | None = None,
    category: str = "company",
    max_pages: int = 3,
    recent_days: int = 60,
    fetch_snippet: bool = True,
    max_workers: int = 8,
    per_request_timeout: float = 10.0,
    page_delay: float = 0.2,
) -> str:
    items: List[Dict[str, Any]] = []
    now = dt.datetime.utcnow()
    cutoff = now - dt.timedelta(days=max(1, int(recent_days)))
    sess, timeout = _session(per_request_timeout)

    # 1) 목록 수집
    rows: list[dict] = []
    for page in range(1, max_pages + 1):
        url = f"{BASE}/{category}_list.naver?&page={page}"
        html = _fetch_html(sess, url, timeout)
        if not html: break
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.type_1") or soup.select_one("table")
        if not table: break

        for tr in table.select("tr"):
            tds = tr.find_all("td")
            if len(tds) < 5: continue
            title = _clean(tds[0].get_text(" ")) if tds[0] else ""
            a = tds[0].find("a")
            link = _abs(a.get("href") if a else "")
            right = _clean(tds[1].get_text(" ")) if tds[1] else ""
            firm, analyst = None, None
            if right:
                parts = [p.strip() for p in right.replace("|","/").split("/") if p.strip()]
                if len(parts)>=1: firm = parts[0]
                if len(parts)>=2: analyst = parts[1]
            opinion = _clean(tds[2].get_text(" ")) if len(tds)>2 else ""
            target  = _clean(tds[3].get_text(" ")) if len(tds)>3 else ""
            date_raw= _clean(tds[4].get_text(" ")) if len(tds)>4 else ""
            date    = _parse_date(date_raw)
            if not _keep_by_date(date, cutoff):  # 1차 기간 필터
                continue
            rows.append({"title":title,"link":link,"firm":firm,"analyst":analyst,
                         "opinion":opinion,"target":target,"date":date})
        time.sleep(page_delay)

    # 2) 상세 스니펫 병렬 수집
    if fetch_snippet and rows:
        def task(r: dict) -> dict:
            html = _fetch_html(sess, r["link"], timeout) if r.get("link") else None
            r["snippet"] = _extract_snippet(html or "", 800)
            return r
        with ThreadPoolExecutor(max_workers=max(1,int(max_workers))) as ex:
            futs = [ex.submit(task, r.copy()) for r in rows]
            for f in as_completed(futs):
                try: r = f.result()
                except Exception: r = None
                if r and _match_query(r["title"], r.get("snippet",""), query):
                    items.append(r)
    else:
        for r in rows:
            if _match_query(r["title"], "", query):
                r["snippet"] = ""
                items.append(r)

    return json.dumps({
        "fetched_at": now.isoformat()+"Z",
        "category": category,
        "query": query,
        "count": len(items),
        "items": items
    }, ensure_ascii=False)

def summarize_broker_reports_with_gemini(
    reports_json: str | dict,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.2,
    max_output_tokens: int = 1536,
    group_size: int = 5,   # ✅ 5개씩 묶어서 호출
    per_item_snippet_limit: int = 900
) -> str:
    import datetime as _dt
    import google.generativeai as genai

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return json.dumps({"error": "GOOGLE_API_KEY not set"}, ensure_ascii=False)
    genai.configure(api_key=api_key)

    src = json.loads(reports_json) if isinstance(reports_json, str) else reports_json
    items = (src or {}).get("items", [])
    if not items:
        return json.dumps({"summarized_at": _dt.datetime.utcnow().isoformat()+"Z",
                           "count": 0, "items": [], "overall_summary": ""}, ensure_ascii=False)

    # 1) 그룹 요약
    out_items: list[dict] = items.copy()
    summaries: list[str] = []
    for i in range(0, len(items), group_size):
        chunk = items[i:i+group_size]
        lines = []
        for idx, it in enumerate(chunk, start=1):
            snip = (it.get("snippet") or "")[:per_item_snippet_limit]
            lines.append(
                f"[{idx}] 제목: {it.get('title','')}\n증권사/애널: {it.get('firm','')}/{it.get('analyst','')}\n"
                f"의견/목표가: {it.get('opinion','')}/{it.get('target','')}\n일자: {it.get('date','')}\n"
                f"본문:\n{snip}\n"
            )
        prompt = (
            "다음 최대 5건의 증권사 리포트를 각각 3~5줄 bullet로 요약해줘. 각 항목은 [n] 헤더로 구분되며, "
            "각 항목별로 (1) 핵심 포인트(근거 1개), (2) 실적/가이던스 핵심치, (3) 의견/목표가 변화, (4) 리스크 1줄을 포함해."
            "\n\n" + "\n\n".join(lines)
        )
        resp = genai.GenerativeModel(model_name).generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature, max_output_tokens=max_output_tokens
            )
        )
        summaries.append((resp.text or "").strip())

    # 2) 요약을 개별 항목에 다시 매핑
    #    (간단 규칙: 그룹 요약을 '\n\n[숫자]' 기준으로 split)
    import re
    cur = 0
    for grp_text in summaries:
        # [1] ... [2] ... 형태로 분해
        parts = re.split(r"\n\s*\[\d+\]\s*", "\n[1]\n" + grp_text.strip())
        for p in parts[1:]:
            if cur < len(out_items):
                out_items[cur]["summary"] = p.strip()
                cur += 1

    # 3) 전체 종합 코멘트 1회 호출
    joined = "\n\n".join(
        [f"- [{i.get('date','')}] {i.get('title','')} — {i.get('firm','')}: {i.get('summary','')}" for i in out_items[:12]]
    )[:6000]
    overall_prompt = (
        "다음 요약을 바탕으로 최근 리포트 흐름을 6~8줄로 정리해줘. "
        "구성: (1) 공통 테마 (2) 상/하향 포인트 (3) 주요 리스크 (4) 결론(중립적 행동 제언).\n\n" + joined
    )
    resp2 = genai.GenerativeModel(model_name).generate_content(
        overall_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=max(0.1, temperature-0.1), max_output_tokens=1024
        )
    )
    overall = (resp2.text or "").strip()

    return json.dumps({
        "summarized_at": _dt.datetime.utcnow().isoformat()+"Z",
        "count": len(out_items),
        "items": out_items,
        "overall_summary": overall
    }, ensure_ascii=False)
