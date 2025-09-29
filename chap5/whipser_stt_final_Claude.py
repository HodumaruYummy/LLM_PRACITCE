import os
import sys
import torch
import pandas as pd
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from pyannote.audio import Pipeline
from dotenv import load_dotenv
from pathlib import Path
import logging
from typing import Tuple, Optional
import warnings

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 경고 메시지 필터링
warnings.filterwarnings("ignore", category=FutureWarning)

class STTDiarizationPipeline:
    """STT와 화자분리를 수행하는 파이프라인 클래스"""
    
    def __init__(self, ffmpeg_path: Optional[str] = None, language: str = "ko"):
        """
        초기화
        Args:
            ffmpeg_path: ffmpeg 실행파일 경로 (선택사항)
            language: 음성 인식 언어 (기본값: "ko" 한국어)
        """
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.language = language
        
        # .env 파일 로드
        load_dotenv()
        
        # ffmpeg 경로 설정
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            os.environ["PATH"] += os.pathsep + ffmpeg_path
        
        logger.info(f"디바이스: {self.device}")
        logger.info(f"데이터 타입: {self.dtype}")
        logger.info(f"언어 설정: {self.language}")
    
    def _validate_audio_file(self, audio_path: str) -> bool:
        """오디오 파일 존재 및 유효성 검사"""
        if not os.path.exists(audio_path):
            logger.error(f"오디오 파일을 찾을 수 없습니다: {audio_path}")
            return False
        
        valid_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
        if Path(audio_path).suffix.lower() not in valid_extensions:
            logger.warning(f"지원하지 않는 파일 형식일 수 있습니다: {Path(audio_path).suffix}")
        
        return True
    
    def whisper_stt(
        self,
        audio_file_path: str,
        output_file_path: str = "./output.csv",
        model_id: str = "openai/whisper-large-v3-turbo",
        use_chunking: bool = False,
        chunk_length: int = 10,
        stride_length: int = 2
    ) -> Tuple[dict, pd.DataFrame]:
        """
        Whisper로 STT 수행 후 CSV 저장
        
        Args:
            audio_file_path: 오디오 파일 경로
            output_file_path: 출력 CSV 파일 경로
            model_id: Whisper 모델 ID
            use_chunking: 청킹 사용 여부 (긴 오디오용, 실험적 기능)
            chunk_length: 청크 길이(초) - use_chunking=True일 때만 사용
            stride_length: 스트라이드 길이(초) - use_chunking=True일 때만 사용
        
        Returns:
            (result, dataframe): STT 결과와 DataFrame
        """
        if not self._validate_audio_file(audio_file_path):
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_file_path}")
        
        try:
            logger.info("Whisper 모델 로딩 중...")
            
            # 모델 로딩 (dtype 사용)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id,
                torch_dtype=self.dtype,  # dtype으로 변경
                low_cpu_mem_usage=True,
                use_safetensors=True,
            )
            model.to(self.device)
            
            processor = AutoProcessor.from_pretrained(model_id)
            
            # 파이프라인 설정
            pipeline_kwargs = {
                "model": model,
                "tokenizer": processor.tokenizer,
                "feature_extractor": processor.feature_extractor,
                "torch_dtype": self.dtype,  # dtype으로 변경
                "device": self.device,
                "return_timestamps": True,
            }
            
            # 언어 및 작업 설정 (경고 해결)
            generation_kwargs = {
                "language": self.language,
                "task": "transcribe"  # 번역이 아닌 전사로 명시
            }
            
            # 청킹 사용 시 (실험적 기능)
            if use_chunking:
                logger.warning("청킹 모드는 실험적 기능입니다. 정확도가 떨어질 수 있습니다.")
                pipeline_kwargs.update({
                    "chunk_length_s": chunk_length,
                    "stride_length_s": stride_length,
                    "ignore_warning": True  # 청킹 경고 무시
                })
            
            # 파이프라인 생성
            asr = pipeline("automatic-speech-recognition", **pipeline_kwargs)
            
            logger.info("STT 처리 시작...")
            result = asr(audio_file_path, generate_kwargs=generation_kwargs)
            
            # DataFrame 변환
            df = self._whisper_to_dataframe(result, output_file_path)
            
            logger.info(f"STT 완료. {len(df)}개 세그먼트 생성")
            return result, df
            
        except Exception as e:
            logger.error(f"STT 처리 중 오류 발생: {str(e)}")
            raise
    
    def _whisper_to_dataframe(self, result: dict, output_file_path: str) -> pd.DataFrame:
        """Whisper 결과를 DataFrame으로 변환하고 저장"""
        rows = []
        
        for chunk in result.get("chunks", []):
            timestamp = chunk.get("timestamp", [None, None])
            start = timestamp[0] if timestamp[0] is not None else 0
            end = timestamp[1] if timestamp[1] is not None else start
            text = chunk.get("text", "").strip()
            
            if text:  # 빈 텍스트 제외
                rows.append([start, end, text])
        
        df = pd.DataFrame(rows, columns=["start", "end", "text"])
        
        # 출력 디렉토리 생성
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        
        # CSV 저장
        df.to_csv(output_file_path, index=False, sep="|", encoding="utf-8")
        return df
    
    def speaker_diarization(
        self,
        audio_file_path: str,
        output_rttm_file_path: str,
        output_csv_file_path: str,
        model_name: str = "pyannote/speaker-diarization-3.1"
    ) -> pd.DataFrame:
        """
        화자 분리 수행
        
        Args:
            audio_file_path: 오디오 파일 경로
            output_rttm_file_path: RTTM 출력 파일 경로
            output_csv_file_path: CSV 출력 파일 경로
            model_name: 화자 분리 모델 이름
        
        Returns:
            DataFrame: 화자 분리 결과
        """
        if not self._validate_audio_file(audio_file_path):
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_file_path}")
        
        # Hugging Face 토큰 확인
        hf_token = os.getenv("HUGGING_FACE_TOKEN") or os.getenv("UGGING_FACE_TOKEN")
        if not hf_token:
            raise RuntimeError(
                "Hugging Face 토큰이 필요합니다.\n"
                ".env 파일에 'HUGGING_FACE_TOKEN=hf_xxxxx' 형태로 설정하거나\n"
                "환경변수로 설정해주세요."
            )
        
        try:
            logger.info("화자 분리 모델 로딩 중...")
            
            pipeline_sd = Pipeline.from_pretrained(
                model_name,
                use_auth_token=hf_token,
            )
            
            if torch.cuda.is_available():
                pipeline_sd.to(torch.device("cuda"))
                logger.info("CUDA 사용 가능")
            else:
                logger.info("CUDA 사용 불가능 - CPU 사용")
            
            logger.info("화자 분리 처리 시작...")
            diarization = pipeline_sd(audio_file_path)
            
            # 출력 디렉토리 생성
            os.makedirs(os.path.dirname(output_rttm_file_path), exist_ok=True)
            os.makedirs(os.path.dirname(output_csv_file_path), exist_ok=True)
            
            # RTTM 파일 저장
            with open(output_rttm_file_path, "w", encoding="utf-8") as rttm:
                diarization.write_rttm(rttm)
            
            # DataFrame으로 변환
            df_grouped = self._process_rttm_to_dataframe(output_rttm_file_path, output_csv_file_path)
            
            logger.info(f"화자 분리 완료. {len(df_grouped)}개 세그먼트 생성")
            return df_grouped
            
        except Exception as e:
            logger.error(f"화자 분리 처리 중 오류 발생: {str(e)}")
            raise
    
    def _process_rttm_to_dataframe(self, rttm_file_path: str, output_csv_path: str) -> pd.DataFrame:
        """RTTM 파일을 처리하여 연속 구간 병합 후 DataFrame 반환"""
        try:
            df_rttm = pd.read_csv(
                rttm_file_path,
                sep=" ",
                header=None,
                names=[
                    "type", "file", "chnl", "start", "duration",
                    "C1", "C2", "speaker_id", "C3", "C4",
                ],
            )
            
            if df_rttm.empty:
                logger.warning("화자 분리 결과가 비어있습니다.")
                return pd.DataFrame(columns=["start", "end", "speaker_id", "duration"])
            
            # 종료 시각 계산
            df_rttm["end"] = df_rttm["start"] + df_rttm["duration"]
            
            # 연속 구간 번호 부여
            df_rttm["number"] = 0
            
            for i in range(1, len(df_rttm)):
                prev_speaker = df_rttm.iloc[i-1]["speaker_id"]
                curr_speaker = df_rttm.iloc[i]["speaker_id"]
                
                if curr_speaker != prev_speaker:
                    df_rttm.iloc[i, df_rttm.columns.get_loc("number")] = df_rttm.iloc[i-1]["number"] + 1
                else:
                    df_rttm.iloc[i, df_rttm.columns.get_loc("number")] = df_rttm.iloc[i-1]["number"]
            
            # 연속 구간별 병합
            df_grouped = df_rttm.groupby("number").agg({
                "start": "min",
                "end": "max",
                "speaker_id": "first",
            }).reset_index(drop=True)
            
            df_grouped["duration"] = df_grouped["end"] - df_grouped["start"]
            
            # CSV 저장
            df_grouped.to_csv(output_csv_path, index=False, encoding="utf-8")
            return df_grouped
            
        except Exception as e:
            logger.error(f"RTTM 처리 중 오류 발생: {str(e)}")
            raise
    
    def merge_stt_and_diarization(
        self,
        df_stt: pd.DataFrame,
        df_rttm: pd.DataFrame,
        final_output_csv_path: str
    ) -> pd.DataFrame:
        """
        STT 결과와 화자 분리 결과를 병합
        
        Args:
            df_stt: STT DataFrame
            df_rttm: 화자 분리 DataFrame
            final_output_csv_path: 최종 출력 파일 경로
        
        Returns:
            DataFrame: 병합된 결과
        """
        logger.info("STT 결과와 화자 분리 결과 병합 중...")
        
        # 텍스트 컬럼 초기화
        df_rttm = df_rttm.copy()
        df_rttm["text"] = ""
        
        # STT 청크별로 가장 많이 겹치는 화자 구간 찾기
        for _, row_stt in df_stt.iterrows():
            best_overlap = 0
            best_idx = None
            
            for idx, row_rttm in df_rttm.iterrows():
                # 겹치는 시간 계산
                overlap_start = max(row_stt["start"], row_rttm["start"])
                overlap_end = min(row_stt["end"], row_rttm["end"])
                overlap_duration = max(0, overlap_end - overlap_start)
                
                if overlap_duration > best_overlap:
                    best_overlap = overlap_duration
                    best_idx = idx
            
            # 가장 많이 겹치는 구간에 텍스트 추가
            if best_idx is not None and best_overlap > 0:
                if df_rttm.at[best_idx, "text"]:
                    df_rttm.at[best_idx, "text"] += " " + row_stt["text"]
                else:
                    df_rttm.at[best_idx, "text"] = row_stt["text"]
        
        # 최종 결과 정리
        df_final = df_rttm[["start", "end", "speaker_id", "duration", "text"]].copy()
        df_final = df_final[df_final["text"].str.strip() != ""]  # 빈 텍스트 제거
        
        # 출력 디렉토리 생성
        os.makedirs(os.path.dirname(final_output_csv_path), exist_ok=True)
        
        # 최종 CSV 저장
        df_final.to_csv(final_output_csv_path, index=False, sep="|", encoding="utf-8")
        
        logger.info(f"병합 완료. 최종 {len(df_final)}개 세그먼트")
        return df_final
    
    def process_audio(
        self,
        audio_file_path: str,
        output_dir: str = "./output",
        base_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        전체 파이프라인 실행
        
        Args:
            audio_file_path: 오디오 파일 경로
            output_dir: 출력 디렉토리
            base_name: 기본 파일명 (없으면 오디오 파일명 사용)
        
        Returns:
            DataFrame: 최종 결과
        """
        if not base_name:
            base_name = Path(audio_file_path).stem
        
        # 출력 파일 경로 설정
        stt_output = os.path.join(output_dir, f"{base_name}_stt.csv")
        rttm_output = os.path.join(output_dir, f"{base_name}.rttm")
        rttm_csv_output = os.path.join(output_dir, f"{base_name}_diarization.csv")
        final_output = os.path.join(output_dir, f"{base_name}_final.csv")
        
        try:
            # 1. STT 수행
            logger.info("=== STT 처리 시작 ===")
            _, df_stt = self.whisper_stt(audio_file_path, stt_output)
            
            # 2. 화자 분리 수행
            logger.info("=== 화자 분리 처리 시작 ===")
            df_rttm = self.speaker_diarization(audio_file_path, rttm_output, rttm_csv_output)
            
            # 3. 결과 병합
            logger.info("=== 결과 병합 시작 ===")
            df_final = self.merge_stt_and_diarization(df_stt, df_rttm, final_output)
            
            logger.info(f"=== 전체 처리 완료 ===")
            logger.info(f"최종 결과: {final_output}")
            
            return df_final
            
        except Exception as e:
            logger.error(f"파이프라인 처리 중 오류 발생: {str(e)}")
            raise


def main():
    """메인 실행 함수"""
    # 설정
    audio_file_path = r"C:\Users\전산2실 PC\Downloads\PRACTICE1\chap5\싼기타_비싼기타.mp3"
    output_dir = r"C:\Users\전산2실 PC\Downloads\PRACTICE1\chap5\output"
    ffmpeg_path = r"C:\Users\전산2실 PC\Downloads\PRACTICE1\ffmpeg\bin"
    
    try:
        # 파이프라인 초기화
        pipeline = STTDiarizationPipeline(ffmpeg_path=ffmpeg_path)
        
        # 전체 처리 실행
        df_final = pipeline.process_audio(audio_file_path, output_dir)
        
        # 결과 출력
        print("\n=== 최종 결과 ===")
        print(df_final.to_string(index=False))
        
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()