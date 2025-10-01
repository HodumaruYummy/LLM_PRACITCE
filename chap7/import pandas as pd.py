import pandas as pd

# 파일 이름 (필요시 경로 포함하여 수정)
input_filename = 'case_study.csv'
output_filename = 'case_study_reordered.csv'

# 재정렬하고 싶은 열의 순서를 리스트로 정의합니다.
# 요청하신 순서를 바탕으로 오타(Cl5DL8 -> CL5, DL8) 및 대소문자를 수정했습니다.
desired_order = [
    'GL6', 'GL8', 'CL10', 'GL5', 'DL10', 'GL7', 'GL3', 'GL2', 'CL4', 'CL6',
    'CL2', 'DL6', 'DL3', 'GL9', 'GL1', 'CL7', 'CL9', 'CL1', 'CL5', 'DL8',
    'DL1', 'GL4', 'DL4'
]

try:
    # CSV 파일을 읽어옵니다.
    df = pd.read_csv(input_filename)
    print("파일을 성공적으로 읽었습니다.")
    print("기존 열 순서:", df.columns.tolist())

    # 기존 데이터프레임의 열 목록을 가져옵니다.
    original_columns = df.columns.tolist()

    # 최종적으로 사용할 열 순서를 결정합니다.
    # desired_order에 있는 열을 먼저 배치하고,
    # 여기에 포함되지 않은 나머지 열들은 원래 순서대로 뒤에 추가합니다.
    remaining_columns = [col for col in original_columns if col not in desired_order]
    final_order = desired_order + remaining_columns

    # 데이터프레임의 열 순서를 변경합니다.
    df_reordered = df[final_order]
    print("\n열 순서를 성공적으로 재정렬했습니다.")
    print("새로운 열 순서:", df_reordered.columns.tolist())

    # 결과를 새로운 CSV 파일로 저장합니다.
    df_reordered.to_csv(output_filename, index=False)
    print(f"\n결과가 '{output_filename}' 파일로 저장되었습니다.")

except FileNotFoundError:
    print(f"오류: '{input_filename}' 파일을 찾을 수 없습니다. 파일이 코드와 동일한 위치에 있는지 확인해주세요.")
except Exception as e:
    print(f"오류가 발생했습니다: {e}")