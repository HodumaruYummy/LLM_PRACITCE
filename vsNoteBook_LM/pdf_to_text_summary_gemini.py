# app.py
import os
import argparse
from datetime import datetime

import google.generativeai as genai
from dotenv import load_dotenv
import fitz  # PyMuPDF


def load_api_key():
    """
    GOOGLE_API_KEY는 우선순위대로 읽습니다:
    1) 환경변수 GOOGLE_API_KEY (Codespaces 시크릿 권장)
    2) .env 파일의 GOOGLE_API_KEY
    """
    load_dotenv()  # .env 있으면 읽음
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY가 설정되어 있지 않습니다. "
                         "Codespaces 시크릿 또는 .env 파일을 확인하세요.")
    genai.configure(api_key=api_key)


def pdf_to_text(pdf_file_path: str, output_dir: str = "output") -> str:
    """
    PDF 본문에서 상/하단 여백(헤더/푸터) 제거 후 텍스트 추출 → txt 저장 경로 반환
    """
    doc = fitz.open(pdf_file_path)
    header_height = 80
    footer_height = 80
    full_text = ""

    for page in doc:
        rect = page.rect
        text = page.get_text(clip=(0, header_height, rect.width, rect.height - footer_height))
        full_text += text + "\n" + "-" * 50 + "\n"

    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(pdf_file_path))[0]
    out_path = os.path.join(output_dir, f"{base}_with_preprocessing.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    return out_path


def summarize_text_with_gemini(text: str, model_name: str = "gemini-2.5-pro") -> str:
    """
    Gemini 모델을 이용해 요약 텍스트 생성
    """
    model = genai.GenerativeModel(model_name)
    prompt = f"""
너는 다음 글을 요약하는 봇이다. 아래 글을 읽고, 저자의 문제 인식과 주장을 파악하고, 주요 내용을 요약해라.
작성해야 하는 포맷은 다음과 같다:

# 제목
## 저자의 문제 인식 및 주장 (15문장 이내)
## 저자 소개

==============================이하 텍스트 ============================
{text}
"""
    response = model.generate_content(prompt)

    try:
        return response.candidates[0].content.parts[0].text
    except (IndexError, AttributeError) as e:
        return f"요약 생성에 실패했습니다. (응답 파싱 오류: {e})"


def summarize_txt_file(txt_path: str, output_dir: str = "output",
                       model_name: str = "gemini-2.5-pro") -> str:
    with open(txt_path, "r", encoding="utf-8") as f:
        src = f.read()

    summary = summarize_text_with_gemini(src, model_name=model_name)

    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(output_dir, f"summary_{now}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(summary)
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="PDF → 텍스트 → Gemini 요약 파이프라인"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default="블루멤버스_개인회원_가이드북.pdf",
        help="요약할 PDF 파일 경로"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro"),
        help="Gemini 모델명 (기본: gemini-2.5-pro)"
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="output",
        help="결과 저장 폴더 (기본: output)"
    )
    args = parser.parse_args()

    load_api_key()

    if not os.path.exists(args.pdf):
        print(f"❌ 오류: '{args.pdf}' 파일이 존재하지 않습니다.")
        return

    print(f"[1] PDF → 텍스트 변환 중: {args.pdf}")
    txt_file = pdf_to_text(args.pdf, output_dir=args.outdir)
    print(f"   ✅ 텍스트 저장: {txt_file}")

    print(f"[2] 텍스트 요약 중... (model={args.model})")
    summary_path = summarize_txt_file(txt_file, output_dir=args.outdir, model_name=args.model)
    print(f"   ✅ 요약 완료: {summary_path}")


if __name__ == "__main__":
    main()
