
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
REQ = ROOT / "requirements.txt"
README = ROOT / "README.md"

def load_requirements(path: Path) -> list[str]:
    pkgs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # tolerate version pins/extras but keep simple 'name' for pip install one-liner
        # If you prefer to keep exact pins, comment the split and use s as-is.
        s = s.split(";")[0].strip()  # drop env markers
        pkgs.append(s)
    # preserve order as in requirements.txt
    return pkgs

def build_pip_install(pkgs: list[str]) -> str:
    return "pip install " + " ".join(pkgs)

def update_readme(readme_path: Path, command: str) -> None:
    text = readme_path.read_text(encoding="utf-8")

    # Replace the first bash code block that starts with "pip install"
    pattern = re.compile(r"```bash\s*?\n\s*pip install[^\n]*\n```", re.MULTILINE)
    replacement = f"```bash\n{command}\n```"

    if pattern.search(text):
        new_text = pattern.sub(replacement, text, count=1)
    else:
        # If not found, append under a standard heading
        addition = "\n\n### 설치 명령어 자동 생성\n" + replacement + "\n"
        new_text = text + addition

    readme_path.write_text(new_text, encoding="utf-8")

def main():
    if not REQ.exists():
        raise SystemExit("requirements.txt not found")
    if not README.exists():
        raise SystemExit("README.md not found")

    pkgs = load_requirements(REQ)
    cmd = build_pip_install(pkgs)
    update_readme(README, cmd)
    print("README.md updated from requirements.txt")
    print(cmd)

if __name__ == "__main__":
    main()
