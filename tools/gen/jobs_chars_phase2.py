"""Phase 2: blink/mouth variants for Yunseul expressions, expression edits for supporting cast.
Phase 3 (--phase3): variants for supporting cast expressions."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASE3 = "--phase3" in sys.argv

KEEP = ("Keep everything else exactly identical: eyebrows, the rest of the face, head position and angle, hair and "
        "bangs, accessories, clothes, hands, pose, framing, canvas size, colors, lighting and line style. Do not move, "
        "rescale, recrop or redraw anything else. Keep the transparent background.")


def pre(who: str) -> str:
    return ("Edit the attached image with your built-in image_gen tool. It is a visual novel character sprite "
            f"({who}); the result is an animation frame layered over the original, so pixel alignment is critical. ")


BLINK = ("Change ONLY the eyes: close both eyes completely as in the middle of a natural blink — relaxed closed "
         "upper eyelids with eyelashes, following the same eye shape, position and emotion as now. ")
M1 = ("Change ONLY the mouth: part the lips slightly as if in the middle of speaking a soft syllable — a small, "
      "natural opening with a hint of the upper teeth, keeping the same mouth position and the same emotion. ")
M2 = ("Change ONLY the mouth: open it naturally as if in the middle of speaking the vowel 'a' — a medium opening "
      "showing the upper teeth and tongue, keeping the same mouth position and the same emotion. ")

MOUTH_FLAVOR = {
    "neutral": "",
    "smile": "The corners of the mouth stay raised in her teasing smile while talking. ",
    "laugh": "She is laughing while talking, the mouth corners stay lifted in a happy smile; the eyes stay closed "
             "in happy crescents. ",
    "gentle": "The mouth keeps its soft, warm smile while talking. ",
    "pout": "She talks grumpily; the mouth stays small and sulky. ",
    "angry": "She speaks angrily through tense lips; the mouth corners are pulled down a little. ",
    "surprised": "A startled, slightly rounded mouth shape. ",
    "embarrassed": "She speaks shyly and awkwardly; the mouth is small and a little wavy. ",
    "sad": "She speaks sadly; the mouth corners droop slightly. ",
    "cry": "She speaks while crying; the lips tremble and the mouth corners are pulled down. ",
    "serious": "She speaks firmly and calmly. ",
}

jobs = []
Y = "art_src/chars/yunseul"
if not PHASE3:
    exprs = ["neutral", "smile", "laugh", "gentle", "pout", "angry", "surprised", "embarrassed", "sad", "cry", "serious"]
    for e in exprs:
        src = f"{Y}/master.png" if e == "neutral" else f"{Y}/expr/{e}.png"
        who = "Ha Yunseul, 17"
        if e != "laugh":
            extra = "Tears remain on the lashes. " if e == "cry" else ""
            jobs.append({"id": f"ys_{e}_blink", "out": f"{Y}/var/{e}_blink.png", "images": [src],
                         "prompt": pre(who) + BLINK + extra + KEEP})
        for tag, m in (("m1", M1), ("m2", M2)):
            jobs.append({"id": f"ys_{e}_{tag}", "out": f"{Y}/var/{e}_{tag}.png", "images": [src],
                         "prompt": pre(who) + m + MOUTH_FLAVOR[e] + KEEP})

    PRE_EXPR = ("Edit the attached image with your built-in image_gen tool. It is a visual novel character sprite "
                "({who}) and the result will be layered over the original as an expression frame, so alignment is "
                "critical. Change ONLY the facial expression (eyebrows, eyes, mouth, cheeks) as follows: ")
    KEEP_E = ("Keep the head position, head angle, face shape and size, hair, clothes, hands, pose, framing, canvas "
              "size, colors, lighting and line style exactly identical. Do not move, rescale, recrop or redraw "
              "anything else. Keep the transparent background.")
    B = "art_src/chars/bongsun"
    for name, desc in {
        "laugh": "a big hearty laugh with eyes squeezed into happy crescents and a wide closed-mouth grin, cheeks lifted.",
        "sad": "a sad, wistful look: eyes downcast and moist, eyebrows tilted up in the middle, a faint sad smile.",
        "surprised": "surprised: eyes wide open, eyebrows raised high, lips closed.",
        "stern": "a stern scolding look: eyebrows lowered and knitted, sharp eyes, lips pressed firmly.",
        "cry": "crying with emotion: tears streaming down the wrinkled cheeks, eyebrows drawn up, a trembling smile.",
    }.items():
        jobs.append({"id": f"bs_expr_{name}", "out": f"{B}/expr/{name}.png", "images": [f"{B}/master.png"],
                     "prompt": PRE_EXPR.format(who="Kim Bongsun, 78-year-old grandmother") + desc + " " + KEEP_E})
    F = "art_src/chars/father"
    for name, desc in {
        "smile": "a tired but warm, kind smile, eyes softened behind the glasses, mouth closed.",
        "serious": "serious and stern: eyebrows lowered and straight, a firm steady gaze, mouth in a tight line.",
        "sad": "guilty and sad: eyes looking down, eyebrows drawn together, a heavy, regretful look, mouth closed.",
    }.items():
        jobs.append({"id": f"fa_expr_{name}", "out": f"{F}/expr/{name}.png", "images": [f"{F}/master.png"],
                     "prompt": PRE_EXPR.format(who="Seo Jeonghun, 47-year-old engineer") + desc + " " + KEEP_E})
    out = ROOT / "art_work" / "jobs_chars_phase2.json"
else:
    for key, who, exprs in (("bongsun", "Kim Bongsun, 78-year-old grandmother", ["neutral", "laugh", "sad", "surprised", "stern", "cry"]),
                            ("father", "Seo Jeonghun, 47-year-old engineer", ["neutral", "smile", "serious", "sad"])):
        base = f"art_src/chars/{key}"
        pfx = "bs" if key == "bongsun" else "fa"
        for e in exprs:
            src = f"{base}/master.png" if e == "neutral" else f"{base}/expr/{e}.png"
            if e != "laugh":
                jobs.append({"id": f"{pfx}_{e}_blink", "out": f"{base}/var/{e}_blink.png", "images": [src],
                             "prompt": pre(who) + BLINK + KEEP})
            for tag, m in (("m1", M1), ("m2", M2)):
                flavor = "The mouth keeps the same emotion while talking. "
                jobs.append({"id": f"{pfx}_{e}_{tag}", "out": f"{base}/var/{e}_{tag}.png", "images": [src],
                             "prompt": pre(who) + m + flavor + KEEP})
    out = ROOT / "art_work" / "jobs_chars_phase3.json"

out.write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(jobs), "jobs ->", out)
