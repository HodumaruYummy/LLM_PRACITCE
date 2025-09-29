#!/usr/bin/env python3
# pdf_to_text_summary_gemini.py
# ─────────────────────────────────────────────────────────────────────────────
# 목적: 폴더의 PDF(기본: 최신 파일)를 선택해 텍스트 추출 → Gemini로 청크 요약 → 통합 요약 저장
# 실행 예:
#   python pdf_to_text_summary_gemini.py
#   python pdf_to_text_summary_gemini.py --pdf "초등학생을_위한_라즈베리파이.pdf" --chunk-size 4000 --max-chunks 60 --sleep 0.4
#   python pdf_to_text_summary_gemini.py --model gemini-1.5-flash --outdir output
# ─────────────────────────────────────────────────────────────────────────────

import os
import glob
import time
import argparse
from datetime import datetime

import google.generativeai as genai   # Gemini SDK
from dotenv import load_dotenv          # .env 로더
import fitz                             # PyMuPDF (PDF 텍스트 추출)

# ─────────────────────────────────────────────────────────────────────────────
# 1) API 키 로드/설정
# ─────────────────────────────────────────────────────────────────────────────
def load_api_key():
    """GOOGLE_API_KEY를 .env/환경변수에서 읽어 Gemini SDK 초기화."""
    load_dotenv()                       # .env가 있으면 읽음
    api_key = os.getenv("GOOGLE_API_KEY")       # GOOGLE_API_KEY 조회
    if not api_key:
        raise ValueError("GOOGLE_API_KEY가 없습니다. Codespaces 시크릿 또는 .env를 확인하세요.")
    genai.configure(api_key=api_key)            # SDK에 키 설정

# ─────────────────────────────────────────────────────────────────────────────
# 2) 파일 선택/경로 처리
# ─────────────────────────────────────────────────────────────────────────────
def auto_find_latest_pdf() -> str:
    """현재 폴더에서 가장 최근 수정된 PDF 파일명을 반환. 없으면 예외."""
    pdfs = glob.glob("*.pdf")
    if not pdfs:
        raise FileNotFoundError("현재 폴더에 PDF가 없습니다. --pdf로 파일을 지정하세요.")
    return max(pdfs, key=os.path.getmtime)

def ensure_pdf_path(path_str: str | None) -> str:
    """
    --pdf 인자가 비어있으면 최신 PDF 자동 선택.
    인자가 있고 확장자를 생략했다면 .pdf 붙여서 반환.
    """
    if not path_str or not path_str.strip():
        return auto_find_latest_pdf()
    path_str = path_str.strip()
    root, ext = os.path.splitext(path_str)
    return f"{path_str}.pdf" if not ext else path_str

# ─────────────────────────────────────────────────────────────────────────────
# 3) 파일 I/O 유틸
# ─────────────────────────────────────────────────────────────────────────────
def safe_write_text(path: str, text: str):
    """상위 폴더 생성 후 UTF-8 텍스트 저장."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# ─────────────────────────────────────────────────────────────────────────────
# 4) 텍스트 분할(청크) - 수정된 함수
# ─────────────────────────────────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 300, max_chunks: int | None = None) -> list[str]:
    """
    모델 입력 한도/안정성을 고려해 텍스트를 겹침 포함 청크로 분할.
    - chunk_size: 각 청크 길이(문자 기준)
    - overlap: 다음 청크와 겹칠 길이(문맥 보존)
    - max_chunks: 청크 수 상한(과도한 API 호출/메모리 사용 방지)
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        if max_chunks is not None and len(chunks) >= max_chunks:
            print(f"경고: 청크 수가 최대치({max_chunks})에 도달했습니다.")
            break
        
        end = start + chunk_size
        chunks.append(text[start:end])
        
        next_start = start + chunk_size - overlap
        
        if next_start <= start:
            # chunk_size <= overlap 인 경우 등 진행이 멈추는 것을 방지
            start += chunk_size
        else:
            start = next_start
            
    return chunks

# ─────────────────────────────────────────────────────────────────────────────
# 5) PDF → 텍스트(헤더/푸터 제거)
# ─────────────────────────────────────────────────────────────────────────────
def pdf_to_text(pdf_path: str, output_dir: str = "output") -> str:
    """
    각 페이지에서 헤더/푸터(경험값: 80px)를 제외하고 텍스트만 추출.
    결과를 '{원본명}_with_preprocessing.txt'로 저장하고 경로 반환.
    """
    doc = fitz.open(pdf_path)
    header_h, footer_h = 80, 80
    parts = []
    for page in doc:
        rect = page.rect
        text = page.get_text(clip=(0, header_h, rect.width, rect.height - footer_h))
        parts.append(text)
        parts.append("\n" + "-" * 50 + "\n")        # 페이지 구분선
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    out_txt = os.path.join(output_dir, f"{base}_with_preprocessing.txt")
    safe_write_text(out_txt, "".join(parts))
    return out_txt

# ─────────────────────────────────────────────────────────────────────────────
# 6) Gemini 요약(청크/통합)
# ─────────────────────────────────────────────────────────────────────────────
def summarize_chunk_with_gemini(text: str, model_name: str) -> str:
    """단일 청크를 핵심 불릿으로 요약."""
    model = genai.GenerativeModel(model_name)
    prompt = f"""
다음 텍스트 청크의 핵심 주장·근거·용어를 불릿으로 간결히 요약하라.
- 한글 작성
- 원문 용어 유지
- 중복 최소화, 핵심 위주

<청크 시작>
{text}
<청크 끝>
"""
    resp = model.generate_content(prompt)
    return getattr(resp, "text", "").strip() or "(빈 응답)"

def synthesize_final_summary(chunk_bullets: list[str], model_name: str) -> str:
    """여러 청크 요약을 요구 포맷으로 통합."""
    model = genai.GenerativeModel(model_name)
    joined = "\n\n---\n\n".join(chunk_bullets)
    prompt = f"""
너는 PDF 요약 작성자다. 아래 청크 요약 불릿을 통합하여 최종 포맷으로 작성하라.

[요구 포맷]
# 제목
## 저자의 문제 인식 및 주장 (15문장 이내)
## 저자 소개

[청크 요약 불릿]
{joined}
"""
    resp = model.generate_content(prompt)
    return getattr(resp, "text", "").strip() or "요약 생성에 실패했습니다."

def summarize_txt_file(
    txt_path: str,
    output_dir: str = "output",
    model_name: str = "gemini-2.5-pro",
    chunk_size: int = 4000,
    overlap: int = 300,
    max_chunks: int | None = 60,
    sleep_sec: float = 0.4,
) -> str:
    """
    txt 본문을 청크 요약→통합 요약.
    - 청크별 결과를 즉시 `_partial_*.md`에 append (중간 종료 대비)
    - 최종 통합 요약을 `summary_*.txt`로 저장
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        src = f.read()

    chunks = chunk_text(src, chunk_size=chunk_size, overlap=overlap, max_chunks=max_chunks)
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = os.path.join(output_dir, f"_partial_{now}.md")
    final_path = os.path.join(output_dir, f"summary_{now}.txt")

    bullets = []
    with open(temp_path, "a", encoding="utf-8") as wf:
        for i, ch in enumerate(chunks, 1):
            print(f"   ├─ 청크 {i}/{len(chunks)} 요약 중...")
            try:
                b = summarize_chunk_with_gemini(ch, model_name)
            except Exception as e:
                b = f"(청크 {i} 요약 실패: {e})"
            bullets.append(b)
            wf.write(f"## CHUNK {i}\n{b}\n\n---\n\n")
            if sleep_sec > 0 and i < len(chunks):
                time.sleep(sleep_sec)

    print("   ├─ 청크 요약 통합 중...")
    try:
        summary = synthesize_final_summary(bullets, model_name)
    except Exception as e:
        summary = f"요약 통합에 실패했습니다: {e}\n\n---\n[부분 요약]\n" + "\n\n".join(bullets)

    safe_write_text(final_path, summary)
    return final_path

# ─────────────────────────────────────────────────────────────────────────────
# 7) 엔트리포인트
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PDF → 텍스트 → Gemini 요약 파이프라인")
    parser.add_argument("--pdf", type=str, default=None,
                        help="요약할 PDF 경로(미지정 시 현재 폴더에서 '가장 최근 PDF' 자동 선택)")
    parser.add_argument("--model", type=str, default=os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro"),
                        help="Gemini 모델명 (기본: gemini-1.5-pro)")
    parser.add_argument("--outdir", type=str, default="output",
                        help="결과 저장 폴더 (기본: output)")
    parser.add_argument("--chunk-size", type=int, default=4000,
                        help="청크 크기(문자 기준, 기본 4000)")
    parser.add_argument("--overlap", type=int, default=300,
                        help="청크 겹침 길이(기본 300)")
    parser.add_argument("--max-chunks", type=int, default=60,
                        help="최대 청크 수(기본 60)")
    parser.add_argument("--sleep", type=float, default=0.4,
                        help="청크 사이 대기시간(초, 기본 0.4)")
    args = parser.parse_args()

    load_api_key()
    pdf_path = ensure_pdf_path(args.pdf)
    if not os.path.exists(pdf_path):
        print(f"❌ 오류: '{pdf_path}' 파일이 존재하지 않습니다.")
        return

    print(f"[1] PDF → 텍스트 변환 중: {pdf_path}")
    txt_file = pdf_to_text(pdf_path, output_dir=args.outdir)
    print(f"   ✅ 텍스트 저장: {txt_file}")

    print(f"[2] 텍스트 요약 중... (model={args.model})")
    summary_path = summarize_txt_file(
        txt_file,
        output_dir=args.outdir,
        model_name=args.model,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        max_chunks=args.max_chunks,
        sleep_sec=args.sleep,
    )
    print(f"   ✅ 요약 완료: {summary_path}")

if __name__ == "__main__":
    main()