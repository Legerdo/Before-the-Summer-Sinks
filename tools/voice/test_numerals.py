import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_voices import numerals_to_digits  # noqa: E402

CASES = {
    "오늘 걸로 쉰다섯.": "오늘 걸로 55.",
    "우리 둘 다 열일곱인데.": "우리 둘 다 17인데.",
    "쉰여섯 번째.": "56 번째.",
    "내일은 늦잠 자도 돼. 여섯 시.": "내일은 늦잠 자도 돼. 6 시.",
    "열일곱 개다.": "17 개다.",
    "비상사태니까 다섯 시!": "비상사태니까 5 시!",
    "남은 날은 사십 일.": "남은 날은 40 일.",
    "스물한 살이 되어서도": "21 살이 되어서도",
    "네가 뭘 해.": "네가 뭘 해.",
}
bad = 0
for s, want in CASES.items():
    got = numerals_to_digits(s)
    flag = "ok " if got == want else "BAD"
    bad += got != want
    print(flag, s, "->", got)
sys.exit(1 if bad else 0)
