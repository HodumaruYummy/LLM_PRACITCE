# dart_functions.py
from __future__ import annotations
import os, re, json, math, time
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from functools import lru_cache
import unicodedata as ud
import datetime as dt
from datetime import timedelta
import zipfile
from io import BytesIO

import requests
import pandas as pd
import yfinance as yf
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from xml.etree import ElementTree as ET

DART_API_KEY = os.getenv("DART_API_KEY") or os.getenv("OPEN_DART_API_KEY")
CORPCODE_CACHE = os.path.join(os.path.dirname(__file__), "corpcode.csv")
REPRT_CODES: List[Tuple[str, str]] = [("11013", "1Q"), ("11012", "2Q"), ("11014", "3Q"), ("11011", "4Q")]
_Q_ORDER = {"1Q": 1, "2Q": 2, "3Q": 3, "4Q": 4}
_Q_END_MONTH = {"1Q": 3, "2Q": 6, "3Q": 9, "4Q": 12}

def _session(timeout: float = 10.0) -> tuple[requests.Session, float]:
    s = requests.Session()
    retry = Retry(total=3, connect=3, read=3, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(["GET"]))
    ad = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=16)
    s.mount("http://", ad); s.mount("https://", ad)
    return s, timeout

NORMALIZE_REPL = [ (r"\s+", ""), (r"[’'`]", ""), (r"㈜|주식회사", ""), (r"[\(\)\[\]\-_.]", ""), (r"의", ""), ]
BRAND_FIXES = { "sk하이닉스": "sk하이닉스", "sk hynix": "sk하이닉스", "sk하닉스": "sk하이닉스", "에스케이하이닉스": "sk하이닉스", "삼성의전기": "삼성전기", "삼성 전기": "삼성전기", "lg에너지솔루션": "lg에너지솔루션", "엘지에너지솔루션": "lg에너지솔루션", "현대차": "현대자동차", "카카오": "카카오", "네이버": "네이버", "엘지화학": "lg화학", }

def normalize_name(name: str) -> str:
    if not name: return ""
    x = ud.normalize("NFKC", name).lower()
    for pat, repl in NORMALIZE_REPL: x = re.sub(pat, repl, x)
    return BRAND_FIXES.get(x, x)

def _download_corpcode_to_csv(api_key: str, csv_path: str) -> pd.DataFrame:
    sess, timeout = _session(15.0)
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    params = {"crtfc_key": api_key}
    r = sess.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    try:
        with zipfile.ZipFile(BytesIO(r.content)) as zf: xml_bytes = zf.read('CORPCODE.xml')
        root = ET.fromstring(xml_bytes)
    except (ET.ParseError, zipfile.BadZipFile):
        error_content = r.content.decode('utf-8', errors='ignore')[:500]
        raise RuntimeError(f"DART 고유번호 목록을 받지 못했습니다. DART_API_KEY를 확인해주세요. (서버 응답: {error_content})")
    rows = []
    for el in root.iterfind(".//list"):
        corp_code, corp_name, stock_code = el.findtext("corp_code", "").strip(), el.findtext("corp_name", "").strip(), el.findtext("stock_code", "").strip()
        if corp_code and corp_name: rows.append({"corp_code": corp_code, "corp_name": corp_name, "stock_code": stock_code})
    df = pd.DataFrame(rows).fillna("")
    if not df.empty: df.to_csv(csv_path, index=False, encoding="utf-8")
    return df

@lru_cache(maxsize=1)
def load_corp_table() -> pd.DataFrame:
    if not DART_API_KEY: raise RuntimeError("DART_API_KEY not set")
    if os.path.exists(CORPCODE_CACHE):
        try:
            df = pd.read_csv(CORPCODE_CACHE, dtype=str).fillna("")
            if len(df) > 0: return df
        except Exception: pass
    return _download_corpcode_to_csv(DART_API_KEY, CORPCODE_CACHE)

@dataclass
class CorpHit:
    corp_code: str; corp_name: str; stock_code: str; score: float

def _score_name(query_norm: str, candidate_name: str) -> float:
    cand_norm = normalize_name(candidate_name)
    if not cand_norm or not query_norm: return 0.0
    score = 0.0
    if cand_norm == query_norm: score += 1.0
    if cand_norm.startswith(query_norm) or query_norm.startswith(cand_norm): score += 0.7
    if query_norm in cand_norm: score += 0.6
    gap = abs(len(cand_norm) - len(query_norm))
    score += max(0.0, 0.4 - 0.03 * gap)
    return score

@lru_cache(maxsize=1024)
def get_ticker_from_name_fuzzy(name: str, topk: int = 5) -> Dict[str, Any]:
    df = load_corp_table()
    qn = normalize_name(name)
    if not qn: return {"error": "empty name"}
    for _, row in df.iterrows():
        c_name = row["corp_name"]
        if not c_name: continue
        cand_norm = normalize_name(c_name)
        if qn == cand_norm:
            best_match = {"corp_code": row["corp_code"], "corp_name": c_name, "stock_code": row["stock_code"], "score": 2.0}
            return {"query": name, "best": best_match, "candidates": [best_match]}
    if qn.isdigit() and len(qn) == 6:
        hit = df[df["stock_code"] == qn]
        if not hit.empty:
            row = hit.iloc[0].to_dict()
            best_match = {"corp_code": row["corp_code"], "corp_name": row["corp_name"], "stock_code": row["stock_code"], "score": 2.0}
            return {"query": name, "best": best_match, "candidates": [best_match]}
    candidates: List[CorpHit] = []
    for _, row in df.iterrows():
        c_name = row["corp_name"]
        if not c_name: continue
        s = _score_name(qn, c_name)
        if s > 0: candidates.append(CorpHit(row["corp_code"], c_name, row["stock_code"], s))
    if not candidates: return {"query": name, "best": None, "candidates": []}
    candidates.sort(key=lambda x: x.score, reverse=True)
    best = candidates[0]
    return { "query": name, "best": {"corp_code": best.corp_code, "corp_name": best.corp_name, "stock_code": best.stock_code, "score": round(best.score, 3)}, "candidates": [{"corp_code": c.corp_code, "corp_name": c.corp_name, "stock_code": c.stock_code, "score": round(c.score, 3)} for c in candidates[:max(1, topk)]] }

def _dart_get(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not DART_API_KEY: 
        return {"status": "010", "message": "DART_API_KEY가 설정되지 않았습니다."}
    sess, timeout = _session(10.0)
    base = f"https://opendart.fss.or.kr/api/{endpoint}.json"
    p = {"crtfc_key": DART_API_KEY, **params}
    try:
        r = sess.get(base, params=p, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data
    except requests.exceptions.RequestException as e: 
        return {"status": "900", "message": f"API 요청 중 오류가 발생했습니다: {e}"}
    except json.JSONDecodeError:
        return {"status": "901", "message": "API 응답을 파싱하는 데 실패했습니다 (JSON 형식 오류)."}
    except Exception as e: 
        return {"status": "999", "message": f"알 수 없는 오류가 발생했습니다: {e}"}

@lru_cache(maxsize=256)
def fnltt_singl_acnt_all(corp_code: str, bsns_year: int, reprt_code: str, fs_div: str = "CFS") -> pd.DataFrame:
    data = _dart_get("fnlttSinglAcntAll", {"corp_code": corp_code, "bsns_year": bsns_year, "reprt_code": reprt_code, "fs_div": fs_div})
    if data.get("status") != "000" or "list" not in data: return pd.DataFrame()
    return pd.DataFrame(data["list"]).fillna("")

def extract_accounts(df: pd.DataFrame, names: List[str]) -> Dict[str, Any]:
    out = {}
    if df.empty: return out
    def _pick_one(want: str):
        m = df[df["account_nm"].str.contains(want, na=False)]
        if not m.empty:
            v = m.iloc[-1].get("thstrm_amount", "")
            try: return int(str(v).replace(",", ""))
            except (ValueError, TypeError): return v
        return None
    for want in names: out[want] = _pick_one(want)
    return out

def get_historical_price(ticker: str, target_date: dt.date) -> Dict[str, Any]:
    try:
        start_date = target_date
        end_date = target_date + timedelta(days=5)
        df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
        if df.empty:
            return {"error": f"{target_date.strftime('%Y-%m-%d')} 이후의 거래 기록을 찾을 수 없습니다."}
        first_trade_day = df.index[0]
        close_price = df['Close'].iloc[0]
        volume = df['Volume'].iloc[0]
        return {
            "date": first_trade_day.strftime('%Y-%m-%d'),
            "close": float(close_price),
            "volume": int(volume)
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}

def get_corp_outline(corp_code: str) -> Dict[str, Any]:
    return _dart_get("corpOutline", {"corp_code": corp_code})

def get_dart_indicators_quarterly(symbol: Optional[str] = None, corp_name: Optional[str] = None, years: int = 2, fs_div: str = "CFS") -> Dict[str, Any]:
    if not DART_API_KEY: return {"error": "DART_API_KEY not set"}
    hit = get_ticker_from_name_fuzzy(corp_name or symbol)
    if not hit.get("best"): return {"error": f"기업명 '{corp_name or symbol}'을 찾을 수 없습니다."}
    best = hit["best"]
    corp_code, corp_nm, stock_code = best["corp_code"], best["corp_name"], best["stock_code"]
    this_year = dt.datetime.now().year
    targets = [(y, code, q) for y in range(this_year, this_year - int(years), -1) for code, q in REPRT_CODES]
    price_df = None
    if stock_code and stock_code.strip():
        ticker = f"{stock_code}.KS"
        price_df = yf.download(ticker, period=f"{years+1}y", interval="1d", auto_adjust=True, progress=False)
        if price_df.empty and not ticker.endswith(".KQ"):
            ticker_kq = ticker.replace(".KS", ".KQ")
            price_df_kq = yf.download(ticker_kq, period=f"{years+1}y", interval="1d", auto_adjust=True, progress=False)
            if not price_df_kq.empty: price_df = price_df_kq
    want_accounts = ["매출액", "매출", "영업이익", "당기순이익", "자산총계", "자산", "부채총계", "부채", "자본총계", "자본", "기본주당이익", "EPS", "자기자본이익률", "ROE", "유형자산감가상각비", "무형자산상각비", "영업활동현금흐름"]
    quarters: List[Dict[str, Any]] = []
    for y, reprt_code, qname in targets:
        time.sleep(0.05)
        df = fnltt_singl_acnt_all(corp_code=corp_code, bsns_year=y, reprt_code=reprt_code, fs_div=fs_div)
        if df.empty: continue
        acc = extract_accounts(df, want_accounts)
        op, net, eps = acc.get("영업이익"), acc.get("당기순이익"), acc.get("기본주당이익") or acc.get("EPS")
        ebit = op
        dep, amor = acc.get("유형자산감가상각비"), acc.get("무형자산상각비")
        ebitda = None
        if ebit is not None: ebitda = ebit + (dep or 0) + (amor or 0)
        price, per = None, None
        if price_df is not None and not price_df.empty and eps and eps != 0:
            q_end_month_num = _Q_END_MONTH.get(qname)
            if q_end_month_num:
                q_end_date = pd.Timestamp(year=y, month=q_end_month_num, day=1) + pd.offsets.MonthEnd(0)
                px = price_df.loc[:q_end_date]
                if not px.empty:
                    price = float(px["Close"].iloc[-1])
                    per = price / eps
        quarters.append({ "year": y, "reprt": qname, "sales": acc.get("매출액") or acc.get("매출"), "op": op, "net": net, "assets": acc.get("자산총계") or acc.get("자산"), "debt": acc.get("부채총계") or acc.get("부채"), "equity": acc.get("자본총계") or acc.get("자본"), "eps": eps, "roe": acc.get("자기자본이익률") or acc.get("ROE"), "ebit": ebit, "ebitda": ebitda, "per": per, "price": price, "ocf": acc.get("영업활동현금흐름"), })
    return { "corp": {"corp_code": corp_code, "corp_name": corp_nm, "stock_code": stock_code}, "quarters": quarters, "fs_div": fs_div, "updated_at": dt.datetime.utcnow().isoformat() + "Z" }

@dataclass
class CorpMeta:
    corp_code: str; corp_name: str; stock_code: str
def normalize_financial_payload(payload: Dict[str, Any]) -> Tuple[CorpMeta, pd.DataFrame]:
    corp = payload.get("corp", {}) or {}
    meta = CorpMeta(corp_code=str(corp.get("corp_code", "")), corp_name=str(corp.get("corp_name", "")), stock_code=str(corp.get("stock_code", "")))
    rows: List[Dict[str, Any]] = payload.get("quarters") or []
    out = [{"연도": r.get("year"), "분기": r.get("reprt"), "종가": _safe_float(r.get("price")), "매출": _safe_float(r.get("sales")), "영업이익": _safe_float(r.get("op")), "순이익": _safe_float(r.get("net")), "EBIT": _safe_float(r.get("ebit")), "EBITDA": _safe_float(r.get("ebitda")), "자산": _safe_float(r.get("assets")), "부채": _safe_float(r.get("debt")), "자본": _safe_float(r.get("equity")), "EPS": _safe_float(r.get("eps")), "PER": _safe_float(r.get("per")), "ROE(%)": _safe_float(r.get("roe")), "영업CF": _safe_float(r.get("ocf")), } for r in rows]
    df = pd.DataFrame(out)
    if not df.empty:
        df["연도"] = pd.to_numeric(df["연도"], errors="coerce").astype("Int64")
        df["분기"] = df["분기"].astype("string")
        df["__q__"] = df["분기"].map(_Q_ORDER).fillna(9)
        df = df.sort_values(["연도", "__q__"], ascending=[False, True]).drop(columns="__q__", errors="ignore").reset_index(drop=True)
    return meta, df
def _safe_float(x: Any) -> Optional[float]:
    if x in (None, "NULL", "null", "", "NaN"): return None
    try: return float(x)
    except (ValueError, TypeError): return None
def add_growth_cols(df: pd.DataFrame, cols: List[str] = ["매출", "영업이익", "순이익", "EBIT", "EBITDA"]) -> pd.DataFrame:
    if df.empty: return df
    qrank = df["분기"].map(_Q_ORDER)
    df2 = df.copy()
    df2["__order__"] = (-df2["연도"].astype(float).fillna(0)) * 10 + qrank.fillna(0)
    df2 = df2.sort_values("__order__", ascending=True)
    for c in cols:
        if c not in df2.columns: continue
        df2[f"{c}_QoQ(%)"] = df2[c].pct_change(1) * 100
        df2[f"{c}_YoY(%)"] = df2[c].pct_change(4) * 100
    df2 = df2.sort_values("__order__", ascending=False).drop(columns="__order__", errors="ignore").reset_index(drop=True)
    return df2
def apply_unit_format(df: pd.DataFrame, unit: str = "억원") -> pd.DataFrame:
    if df.empty: return df
    def _fmt_unit(n: Optional[float], u: str) -> Optional[str]:
        if n is None or (isinstance(n, float) and math.isnan(n)): return None
        v = float(n);
        if u == "억원": return f"{v/1e8:,.2f}"
        if u == "조원": return f"{v/1e12:,.3f}"
        return f"{v:,.0f}"
    def _fmt_num(n: Optional[float], fmt: str = ",.0f") -> Optional[str]:
        if n is None or (isinstance(n, float) and math.isnan(n)): return None
        return f"{n:{fmt}}"
    out = df.copy()
    money_cols = [c for c in out.columns if c in ["매출","영업이익","순이익","자산","부채","자본","영업CF", "EBIT", "EBITDA"]]
    for c in money_cols: out[c] = out[c].apply(lambda x: _fmt_unit(x, unit))
    if "종가" in out.columns: out["종가"] = out["종가"].apply(lambda x: _fmt_num(x))
    if "EPS" in out.columns: out["EPS"] = out["EPS"].apply(lambda x: _fmt_num(x))
    if "PER" in out.columns: out["PER"] = out["PER"].apply(lambda x: _fmt_num(x, ",.2f"))
    if "ROE(%)" in out.columns: out["ROE(%)"] = out["ROE(%)"].apply(lambda x: _fmt_num(x, ".2f"))
    growth_cols = [c for c in out.columns if "%" in c];
    for c in growth_cols: out[c] = out[c].apply(lambda x: _fmt_num(x, "+.1f"))
    return out
def get_ticker_from_corp_name(name: str) -> Dict[str, Any]: return get_ticker_from_name_fuzzy(name, topk=5)