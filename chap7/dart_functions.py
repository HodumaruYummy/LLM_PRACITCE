# dart_functions.py
import os
import io
import zipfile
import json
import time
import requests
import pandas as pd
from dotenv import load_dotenv
from xml.etree import ElementTree as ET

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")

BASE = "https://opendart.fss.or.kr/api"

# reprt_code: 11011(1Q), 11012(반기), 11013(3Q), 11014(연간)
REPRT_CODES = [("11011", "1Q"), ("11012", "2Q"), ("11013", "3Q"), ("11014", "4Q")]  # 편의상 4Q=사업보고서

def _req(url: str, params: dict):
    params["crtfc_key"] = DART_API_KEY
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    # DART 표준 코드 체크 (정상: 000)
    if str(data.get("status", "")) not in ("000", "013"):  # 013: 조회된 데이터가 없습니다
        raise RuntimeError(f"DART API error: {data}")
    return data

def download_and_parse_corpcode() -> pd.DataFrame:
    """
    DART 고유번호 전체(압축) 다운로드 후 corp_code/name 매핑 테이블 생성
    """
    url = f"{BASE}/corpCode.xml"
    params = {"crtfc_key": DART_API_KEY}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(r.content))
    xml_bytes = z.read("CORPCODE.xml")
    root = ET.fromstring(xml_bytes)

    rows = []
    for el in root.findall("list"):
        corp_code = el.findtext("corp_code")
        corp_name = el.findtext("corp_name")
        stock_code = el.findtext("stock_code")  # 상장사면 존재
        rows.append({"corp_code": corp_code, "corp_name": corp_name, "stock_code": stock_code})
    return pd.DataFrame(rows)

def find_corp_code(corp_name: str, cache_csv: str = "corpcode.csv") -> dict:
    """
    회사명으로 corp_code 찾기 (캐시 사용)
    """
    if os.path.exists(cache_csv):
        df = pd.read_csv(cache_csv, dtype=str)
    else:
        df = download_and_parse_corpcode()
        df.to_csv(cache_csv, index=False, encoding="utf-8")

    # 완전일치 우선, 없으면 포함검색
    hit = df[df["corp_name"] == corp_name]
    if hit.empty:
        hit = df[df["corp_name"].str.contains(corp_name, na=False)]
    if hit.empty:
        raise ValueError(f"기업명을 찾을 수 없습니다: {corp_name}")

    row = hit.iloc[0].to_dict()
    return {"corp_code": row["corp_code"], "corp_name": row["corp_name"], "stock_code": row.get("stock_code")}

def fnltt_singl_acnt_all(corp_code: str, bsns_year: int, reprt_code: str, fs_div: str = "CFS") -> pd.DataFrame:
    """
    단일회사 전체 재무제표 조회 (연결:CFS / 개별:OFS)
    반환: 계정/금액 테이블
    """
    url = f"{BASE}/fnlttSinglAcntAll.json"
    data = _req(url, {
        "corp_code": corp_code,
        "bsns_year": bsns_year,    # 2015~현재
        "reprt_code": reprt_code,  # 11011/11012/11013/11014
        "fs_div": fs_div           # CFS(연결) or OFS(개별)
    })
    items = data.get("list", []) or []
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    # 금액 컬럼들 숫자화 (thstrm_amount, frmtrm_amount 등)
    for col in [c for c in df.columns if "amount" in c]:
        df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce")
    return df

def extract_accounts(df: pd.DataFrame, accounts: list[str]) -> dict:
    """
    계정명 대소문자/공백 차이를 감안한 안전 추출
    accounts 예: ["당기순이익", "기본주당이익", "자본총계", "자산총계", "지배주주순이익"]
    """
    out = {}
    if df.empty:
        return out
    norm = {str(a).strip().lower(): a for a in df["account_nm"].unique()}
    for want in accounts:
        # 가장 유사한 키워드 우선 탐색
        candidates = [k for k in norm if want.replace(" ", "").lower() in k.replace(" ", "")]
        if candidates:
            key = norm[candidates[0]]
            pick = df[df["account_nm"] == key]
            # 당기 항목 사용(thstrm_amount)
            val = pd.to_numeric(pick["thstrm_amount"], errors="coerce").dropna()
            out[want] = float(val.iloc[0]) if not val.empty else None
        else:
            out[want] = None
    return out
