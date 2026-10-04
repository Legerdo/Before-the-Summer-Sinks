"""Generate synthetic (unconditioned) voice candidates for the supporting cast, then measure them.

Every candidate is an original synthetic speaker sampled by the free Fish model (no reference audio,
no library voice), so no real person's voice is imitated.
Usage: python cast_candidates.py [char ...]   -> art_work/cast/<char>/c_XX.wav + report.json
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fish  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "art_work" / "cast"

CAST = {
    "mother": ("a warm, gentle Korean woman in her late thirties, soft and kind late-night radio voice, calm and loving",
               "여기는 소리실 심야방송, 88.3. 오늘도 깨어 있는 여러분, 반가워요. 창문 열어 두셨나요? 개울 소리가 참 좋은 밤이에요. 우리 딸은 벌써 자고 있네요."),
    "bongsun": ("an elderly Korean grandmother in her late seventies, warm, slightly hoarse and slow, rural Chungcheong dialect",
                "아이구, 왔슈? 이 날씨에 언덕을 걸어 내려왔으면 속이 다 익었을 거여. 자, 사이다 마셔. 이 동네서 처음 온 사람한테 돈 받는 가게 없어."),
    "father": ("a tired but kind Korean man in his late forties, low calm voice, gentle and a little guilty",
               "한결아, 도착했니? 미안하다, 첫날부터 혼자 두고. 수문 공정이 좀 밀려서 오늘은 현장에서 자야 할 것 같아. 밥은 꼭 챙겨 먹고."),
    "grandpa": ("an elderly Korean village chief in his seventies, rustic, hearty and loud, speaking into a village loudspeaker",
                "아아, 마이크 시험 중. 에, 소리실 주민 여러분께 알려 드립니다. 내일은 분교 가을 운동회가 있사오니 한 분도 빠짐없이 나와 주시기 바랍니다."),
    "choi": ("a gruff, stubborn elderly Korean farmer around eighty, rough low voice, rural accent",
             "어, 나여. 아랫말 최가. 딴 게 아니라, 나는 안 나갈 거라고 방송에 좀 해 줘. 나는 여기서 나서 여기서 죽을 겨."),
    "sunja": ("a sweet, gentle elderly Korean grandmother in her eighties, soft and slow voice",
              "윤슬아, 나 순자 할미다. 옛날에 느이 엄마가 틀어 주던 노래 있잖여. 그거 한 번만 틀어 줄 수 있냐. 우리 영숙이 낳고 키운 집이여."),
    "official": ("a formal middle-aged Korean male public official in his fifties, bureaucratic and stiff but not unkind",
                 "주민 여러분, 바쁘신데 참석해 주셔서 감사합니다. 한국수자원공단 소리실댐 건설단입니다. 먼저 이주 일정 변경을 안내드리겠습니다."),
    "villager1": ("a brusque but kind Korean man in his fifties, rural, short-spoken",
                  "윗말 김가다. 할 말은 없고, 그냥 고맙다. 됐지? 이 동네서 오십 년 살았는디, 뭐라고 해야 할지 모르겄다."),
    "villager2": ("a cheerful young Korean man in his late twenties, energetic countryside farmer",
                  "윤슬아! 최씨 할아버지 모셔 왔다! 끝까지 안 나오신다고 버티시다가 라디오에서 니 목소리 듣고서야 일어나시더라."),
    "villager3": ("a warm Korean woman in her early forties, kind, a little emotional",
                  "우리 다온이 첫 걸음마를 여기서 뗐어요. 그거 하나로 충분해요. 소리실에서 보낸 날들, 정말 고마웠어요."),
    "villager4": ("a shy but excited seven-year-old Korean little girl, high childlike voice",
                  "어, 어, 여보세요? 저 다온인데요. 철새 오빠 목소리 듣고 싶어요! 언니 목소리 따라왔어요! 개울아, 반딧불아, 다녀올게!"),
    "villager5": ("a dignified elderly retired Korean male schoolteacher in his seventies, gentle and warm",
                  "분교에서 삼십 년 아이들을 가르쳤습니다. 여름 선생님, 당신 방송 덕분에 밤이 외롭지 않았어요. 고마웠습니다."),
    "anchor": ("a calm professional Korean female news anchor, clear formal broadcast diction",
               "제12호 태풍 미리내가 강한 세력을 유지한 채 북상하고 있습니다. 내일 밤 충청 내륙에 가장 근접할 것으로 보입니다."),
}

N = 6


def gen(args):
    char, i = args
    desc, text = CAST[char]
    d = OUT / char
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"c_{i:02d}.wav"
    if not p.exists():
        fish.tts(f"[{desc}] {text}", p, fmt="wav", sample_rate=44100, temperature=0.8, top_p=0.8)
    (d / "ref_text.txt").write_text(text, encoding="utf-8")
    return str(p)


if __name__ == "__main__":
    chars = sys.argv[1:] or list(CAST.keys())
    jobs = [(c, i) for c in chars for i in range(N)]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(gen, jobs):
            print("ok", r, flush=True)
    manifest = [{"id": f"{c}/c_{i:02d}", "file": str(OUT / c / f"c_{i:02d}.wav"), "text": CAST[c][1]} for c, i in jobs]
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
