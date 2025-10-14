# dart_functions.py
# OpenDART 재무지표 조회 + 종목명(오타/변형 포함)→종목코드 매핑 + 전처리 유틸 (정규화/QoQ·YoY/단위포맷)
from __future__ import annotations

import os
import re
import json
import math
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from functools import lru_cache
import unicodedata as ud
import datetime as _dt

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from xml.etree import ElementTree as ET

# ================================
# 환경변수 / 상수
# ================================
DART_API_KEY = os.getenv("DART_API_KEY") or os.getenv("OPEN_DART_API_KEY")
CORPCODE_CACHE = os.path.join(os.path.dirname(__file__), "corpcode.csv")

# DART 분기 코드 → 라벨
REPRT_CODES: List[Tuple[str, str]] = [
    ("11013", "1Q"), ("11012", "2Q"), ("11014", "3Q"), ("11011", "4Q")
]
_Q_ORDER = {"1Q": 1, "2Q": 2, "3Q": 3, "4Q": 4}

# ================================
# HTTP 세션 (재시도/커넥션 풀)
# ================================
def _session(timeout: float = 10.0) -> tuple[requests.Session, float]:
    s = requests.Session()
    retry = Retry(
        total=3, connect=3, read=3, backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"])
    )
    ad = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=16)
    s.mount("http://", ad); s.mount("https://", ad)
    return s, timeout

# ================================
# 문자열 정규화/교정
# ================================
NORMALIZE_REPL = [
    (r"\s+", ""),             # 공백 제거
    (r"[’'`]", ""),           # 따옴표 제거
    (r"㈜|주식회사", ""),      # 법인표기 제거
    (r"[\(\)\[\]\-_.]", ""),  # 구두점 제거
    (r"의", ""),              # 조사 '의' 제거 → '삼성의전기'→'삼성전기'
]
BRAND_FIXES = {
    "sk하이닉스": "sk하이닉스",
    "sk hynix": "sk하이닉스",
    "sk하닉스": "sk하이닉스",
    "에스케이하이닉스": "sk하이닉스",
    "삼성의전기": "삼성전기",
    "삼성 전기": "삼성전기",
    "lg에너지솔루션": "lg에너지솔루션",
    "엘지에너지솔루션": "lg에너지솔루션",
}
def normalize_name(name: str) -> str:
    if not name:
        return ""
    x = ud.normalize("NFKC", name).lower()
    for pat, repl in NORMALIZE_REPL:
        x = re.sub(pat, repl, x)
    return BRAND_FIXES.get(x, x)

# ================================
# corpcode.xml 다운로드/파싱 + 캐시
# ================================
def _download_corpcode_to_csv(api_key: str, csv_path: str) -> pd.DataFrame:
    sess, timeout = _session(15.0)
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    r = sess.get(url, params={"crtfc_key": api_key}, timeout=timeout)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    rows = []
    for el in root.iterfind(".//list"):
        corp_code = el.findtext("corp_code", "").strip()
        corp_name = el.findtext("corp_name", "").strip()
        stock_code = el.findtext("stock_code", "").strip()
        rows.append({"corp_code": corp_code, "corp_name": corp_name, "stock_code": stock_code})
    df = pd.DataFrame(rows).fillna("")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    return df

@lru_cache(maxsize=1)
def load_corp_table() -> pd.DataFrame:
    if not DART_API_KEY:
        raise RuntimeError("DART_API_KEY not set")
    if os.path.exists(CORPCODE_CACHE):
        try:
            df = pd.read_csv(CORPCODE_CACHE, dtype=str).fillna("")
            if len(df) > 0:
                return df
        except Exception:
            pass
    return _download_corpcode_to_csv(DART_API_KEY, CORPCODE_CACHE)

# ================================
# 종목명/오타 → 최우선 매칭
# ================================
@dataclass
class CorpHit:
    corp_code: str
    corp_name: str
    stock_code: str
    score: float

def _score_name(query_norm: str, candidate_name: str) -> float:
    cand_norm = normalize_name(candidate_name)
    if not cand_norm or not query_norm:
        return 0.0
    score = 0.0
    if cand_norm == query_norm:
        score += 1.0
    if cand_norm.startswith(query_norm) or query_norm.startswith(cand_norm):
        score += 0.7
    if query_norm in cand_norm:
        score += 0.6
    gap = abs(len(cand_norm) - len(query_norm))
    score += max(0.0, 0.4 - 0.03 * gap)
    return score

@lru_cache(maxsize=1024)
def get_ticker_from_name_fuzzy(name: str, topk: int = 5) -> Dict[str, Any]:
    df = load_corp_table()
    qn = normalize_name(name)
    if not qn:
        return {"error": "empty name"}

    # 6자리 숫자면 바로 stock_code 일치
    if qn.isdigit() and len(qn) == 6:
        hit = df[df["stock_code"] == qn]
        if not hit.empty:
            row = hit.iloc[0].to_dict()
            best = {"corp_code": row["corp_code"], "corp_name": row["corp_name"], "stock_code": row["stock_code"], "score": 1.0}
            return {"query": name, "best": best, "candidates": [best]}

    candidates: List[CorpHit] = []
    for _, row in df.iterrows():
        c_name = row["corp_name"]
        if not c_name:
            continue
        s = _score_name(qn, c_name)
        if s <= 0:
            c2 = normalize_name(c_name)
            if c2 and (qn in c2):
                s = 0.55
        if s > 0:
            candidates.append(CorpHit(row["corp_code"], c_name, row["stock_code"], s))

    candidates.sort(key=lambda x: x.score, reverse=True)
    top = candidates[:max(1, topk)]
    best = top[0] if top else None
    if not best:
        return {"query": name, "best": None, "candidates": []}
    return {
        "query": name,
        "best": {"corp_code": best.corp_code, "corp_name": best.corp_name, "stock_code": best.stock_code, "score": round(best.score, 3)},
        "candidates": [{"corp_code": c.corp_code, "corp_name": c.corp_name, "stock_code": c.stock_code, "score": round(c.score, 3)} for c in top]
    }

# ================================
# DART 단일계정 API 래퍼
# ================================
def _dart_get(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not DART_API_KEY:
        return {"error": "DART_API_KEY not set"}
    sess, timeout = _session(10.0)
    base = f"https://opendart.fss.or.kr/api/{endpoint}.json"
    p = {"crtfc_key": DART_API_KEY}
    p.update(params or {})
    r = sess.get(base, params=p, timeout=timeout)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"error": "invalid json", "raw": r.text[:500]}

@lru_cache(maxsize=256)
def fnltt_singl_acnt_all(corp_code: str, bsns_year: int, reprt_code: str, fs_div: str = "CFS") -> pd.DataFrame:
    data = _dart_get("fnlttSinglAcntAll", {
        "corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code, "fs_div": fs_div
    })
    if "list" not in data:
        return pd.DataFrame()
    df = pd.DataFrame(data["list"]).fillna("")
    return df

def extract_accounts(df: pd.DataFrame, names: List[str]) -> Dict[str, Any]:
    out = {}
    if df is None or df.empty:
        return out
    def _pick_one(want: str):
        m = df[df["account_nm"].str.contains(want, na=False)]
        if not m.empty:
            v = m.iloc[-1].get("thstrm_amount", "")
            try:
                return int(str(v).replace(",", ""))
            except Exception:
                return v
        return None
    for want in names:
        out[want] = _pick_one(want)
    return out

# ================================
# 공개 API: 분기 지표 조회 (이름/티커 입력)
# ================================
def get_dart_indicators_quarterly(
    symbol: Optional[str] = None,
    corp_name: Optional[str] = None,
    years: int = 2,
    fs_div: str = "CFS",
) -> Dict[str, Any]:
    """
    분기 단위 핵심 지표(매출/영업이익/순이익/자산/부채/자본/EPS/OCF)를 최근 N년×4분기 반환.
      - symbol: 6자리 종목코드
      - corp_name: 기업명/별칭/오타 허용
      - years: 최근 N년
      - fs_div: CFS(연결) | OFS(별도)
    """
    if not DART_API_KEY:
        return {"error": "DART_API_KEY not set"}

    # 1) 대상 기업 식별
    if not symbol:
        if not corp_name:
            return {"error": "symbol 또는 corp_name 중 하나는 필요합니다."}
        hit = get_ticker_from_name_fuzzy(corp_name)
        best = hit.get("best")
        if not best:
            return {"error": f"기업명을 찾을 수 없습니다: {corp_name}"}
        corp_code = best["corp_code"]; corp_nm = best["corp_name"]; stock_code = best["stock_code"]
    else:
        df = load_corp_table()
        m = df[df["stock_code"] == str(symbol)]
        if m.empty:
            return {"error": f"종목코드를 찾을 수 없습니다: {symbol}"}
        row = m.iloc[0].to_dict()
        corp_code = row["corp_code"]; corp_nm = row["corp_name"]; stock_code = row["stock_code"]

    # 2) 대상 기간
    this_year = _dt.datetime.now().year
    targets = [(y, code, q) for y in range(this_year, this_year - int(years), -1) for code, q in REPRT_CODES]

    # 3) 계정 추출
    want_accounts = ["매출", "영업이익", "당기순이익", "자산", "부채", "자본", "EPS", "영업활동현금흐름"]
    quarters: List[Dict[str, Any]] = []
    for y, reprt_code, qname in targets:
        df = fnltt_singl_acnt_all(corp_code=corp_code, bsns_year=y, reprt_code=reprt_code, fs_div=fs_div)
        acc = extract_accounts(df, want_accounts)
        quarters.append({
            "year": y, "reprt": qname,
            "sales": acc.get("매출"),
            "op": acc.get("영업이익"),
            "net": acc.get("당기순이익"),
            "assets": acc.get("자산"),
            "debt": acc.get("부채"),
            "equity": acc.get("자본"),
            "eps": acc.get("EPS"),
            "ocf": acc.get("영업활동현금흐름"),
        })

    return {
        "corp": {"corp_code": corp_code, "corp_name": corp_nm, "stock_code": stock_code},
        "quarters": quarters,
        "fs_div": fs_div,
        "updated_at": _dt.datetime.utcnow().isoformat() + "Z",
    }

# ================================
# 전처리 유틸: JSON → DataFrame 정규화
# ================================
@dataclass
class CorpMeta:
    corp_code: str
    corp_name: str
    stock_code: str

def normalize_financial_payload(payload: Dict[str, Any]) -> Tuple[CorpMeta, pd.DataFrame]:
    corp = payload.get("corp", {}) or {}
    meta = CorpMeta(
        corp_code=str(corp.get("corp_code", "")),
        corp_name=str(corp.get("corp_name", "")),
        stock_code=str(corp.get("stock_code", "")),
    )
    rows: List[Dict[str, Any]] = (payload.get("quarters") or [])
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "연도": r.get("year"),
            "분기": r.get("reprt"),
            "매출": _safe_float(r.get("sales")),
            "영업이익": _safe_float(r.get("op")),
            "순이익": _safe_float(r.get("net")),
            "자산": _safe_float(r.get("assets")),
            "부채": _safe_float(r.get("debt")),
            "자본": _safe_float(r.get("equity")),
            "EPS": _safe_float(r.get("eps")),
            "영업CF": _safe_float(r.get("ocf")),
        })
    df = pd.DataFrame(out)
    if not df.empty:
        df["연도"] = pd.to_numeric(df["연도"], errors="coerce").astype("Int64")
        df["분기"] = df["분기"].astype("string")
        df["__q__"] = df["분기"].map(_Q_ORDER).fillna(9)
        df = df.sort_values(["연도", "__q__"], ascending=[False, True]).drop(columns="__q__", errors="ignore")
        df = df.reset_index(drop=True)
    return meta, df

def _safe_float(x: Any) -> Optional[float]:
    if x in (None, "NULL", "null", "", "NaN"):
        return None
    try:
        return float(x)
    except Exception:
        return None

# ================================
# QoQ/YoY 계산
# ================================
def add_growth_cols(df: pd.DataFrame, cols: List[str] = ["매출", "영업이익", "순이익"]) -> pd.DataFrame:
    if df.empty:
        return df
    qrank = df["분기"].map(_Q_ORDER)
    df2 = df.copy()
    df2["__order__"] = (-df2["연도"].astype(float)) * 10 + qrank
    df2 = df2.sort_values("__order__", ascending=True)  # 오래된 → 최신
    for c in cols:
        if c not in df2.columns:
            continue
        df2[f"{c}_QoQ(%)"] = df2[c].pct_change(1) * 100
        df2[f"{c}_YoY(%)"] = df2[c].pct_change(4) * 100
    df2 = df2.sort_values("__order__", ascending=False).drop(columns="__order__", errors="ignore").reset_index(drop=True)
    return df2

# ================================
# 단위 변환/표시 포맷
# ================================
def apply_unit_format(df: pd.DataFrame, unit: str = "억원") -> pd.DataFrame:
    if df.empty:
        return df

    def _fmt_unit(n: Optional[float], u: str) -> Optional[str]:
        if n is None or (isinstance(n, float) and math.isnan(n)):
            return None
        try:
            v = float(n)
        except Exception:
            return None
        if u == "억원":
            return f"{v/1e8:,.2f}"
        if u == "조원":
            return f"{v/1e12:,.3f}"
        return f"{v:,.0f}"  # 원

    def _fmt_int(n: Optional[float]) -> Optional[str]:
        if n is None or (isinstance(n, float) and math.isnan(n)):
            return None
        return f"{n:,.0f}"

    out = df.copy()
    money_cols = [c for c in out.columns if c in ["매출","영업이익","순이익","자산","부채","자본","영업CF"]]
    for c in money_cols:
        out[c] = out[c].apply(lambda x: _fmt_unit(x, unit))
    if "EPS" in out.columns:
        out["EPS"] = out["EPS"].apply(_fmt_int)
    return out

# ================================
# 편의 API
# ================================
def get_ticker_from_corp_name(name: str) -> Dict[str, Any]:
    return get_ticker_from_name_fuzzy(name, topk=5)
