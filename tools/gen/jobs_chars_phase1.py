"""Emit phase-1 character jobs: Yunseul expressions + pose bodies, supporting character bases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
Y = "art_src/chars/yunseul"

KEEP = ("Keep her head position, head angle, face shape and size, hair and bangs, the thin braid with red string, "
        "the orange headphones and coiled cable, clothes, hands, pose, framing, canvas size, colors, lighting and "
        "line style exactly identical. Do not move, rescale, recrop or redraw anything else. Keep the transparent background.")

PRE_EXPR = ("Edit the attached image with your built-in image_gen tool. It is a visual novel character sprite "
            "(Ha Yunseul, 17) and the result will be layered over the original as an expression frame, so "
            "alignment is critical. Change ONLY her facial expression (eyebrows, eyes, mouth, cheeks) as follows: ")

EXPRS = {
    "smile": "a confident, teasing smile: the mischievous grin of someone who knows a secret, eyes slightly narrowed "
             "with amusement, one corner of the mouth raised more than the other, mouth closed.",
    "laugh": "a genuine happy laugh with both eyes closed in soft upward crescents and a wide closed-mouth smile "
             "(joyful, carefree), cheeks lifted with a faint pink blush. Mouth stays closed.",
    "gentle": "a soft, warm, gentle smile with relaxed, tender eyes looking at the viewer, a little shy and affectionate, "
              "mouth closed with a small smile.",
    "pout": "an annoyed, sulky pout: eyebrows lowered and pulled together, eyes half-lidded glancing to the side with a "
            "grumpy glare, lips pushed into a small pout, cheeks slightly puffed.",
    "angry": "genuinely angry: eyebrows sharply furrowed, eyes glaring hard at the viewer with a fierce look, "
             "mouth closed in a tight, tense line.",
    "surprised": "startled and flustered: eyes opened wide with small pupils, eyebrows raised high, a light blush on her "
                 "cheeks, lips closed but slightly tense.",
    "embarrassed": "embarrassed and blushing deeply across the cheeks and nose, eyes looking away to her side, eyebrows "
                   "slightly worried, lips pressed together in a small wavy line.",
    "sad": "quietly sad: eyes downcast with heavy eyelids, eyebrows drawn together and tilted up in the middle, "
           "lips pressed softly, melancholic and lonely.",
    "cry": "crying: tears welling up and a few tears streaming down both cheeks, eyes glistening and wet, eyebrows "
           "drawn up in sorrow, a faint red flush around the eyes, lips pressed and trembling.",
    "serious": "serious and determined: a steady, focused gaze straight at the viewer, eyebrows straight and firm, "
               "mouth closed in a calm straight line.",
}

jobs = []
for name, desc in EXPRS.items():
    jobs.append({"id": f"ys_expr_{name}", "out": f"{Y}/expr/{name}.png", "images": [f"{Y}/master.png"],
                 "prompt": PRE_EXPR + desc + " " + KEEP})

PRE_POSE = ("Edit the attached image with your built-in image_gen tool. It is a visual novel character sprite "
            "(Ha Yunseul, 17); the head will be layered from the original, so the head must stay perfectly aligned. "
            "Change ONLY her arms and hands as follows: ")
KEEP_POSE = ("Keep her head, face, expression, hair and bangs, braid, the orange headphones, clothes (same design), "
             "body position, framing, canvas size, colors, lighting and line style exactly identical. Do not move, "
             "rescale or recrop anything. Keep the transparent background.")
POSES = {
    "b": "she now crosses her arms loosely in front of her stomach in a confident, slightly sassy stance; the voice "
         "recorder is no longer visible.",
    "c": "she now gently holds the edge of the left orange headphone ear cup with both hands near her collarbone, "
         "elbows relaxed and close to her body, a tender, thoughtful gesture; the voice recorder is no longer visible.",
}
for outfit in ("uniform", "casual"):
    for pose, desc in POSES.items():
        jobs.append({"id": f"ys_body_{outfit}_{pose}", "out": f"{Y}/body/{outfit}_{pose}.png",
                     "images": [f"{Y}/body/{outfit}_a.png"], "prompt": PRE_POSE + desc + " " + KEEP_POSE})

STYLE_REF = ("Use the attached image ONLY as an art style reference (line quality, cel shading, coloring, rendering "
             "and proportions) and draw a completely different character in exactly that style. ")
FRAME = ("Framing like a visual novel standing sprite: cowboy shot from mid-thigh up, facing the viewer at a slight "
         "three-quarter angle, relaxed standing pose, neutral calm expression with mouth closed and eyes open looking "
         "at the viewer, whole head inside the frame with margin above. Portrait canvas 1024x1536. Fully transparent "
         "background. No text, no watermark.")
jobs.append({"id": "bongsun_base", "out": "art_src/chars/bongsun/master.png", "images": [f"{Y}/master.png"],
             "prompt": "Use your built-in image_gen tool. " + STYLE_REF +
             "Character: Kim Bongsun, a 78-year-old Korean grandmother who runs the tiny village store. Short, tightly "
             "permed gray hair, a kind, deeply wrinkled sun-tanned face with lively sharp eyes and smile lines, small and "
             "slightly stooped. She wears a faded pink floral blouse with small purple flowers, loose patterned dark "
             "work trousers, a plain white cotton apron, and a thin gold ring; her hands are clasped in front of the "
             "apron. " + FRAME})
jobs.append({"id": "father_base", "out": "art_src/chars/father/master.png", "images": [f"{Y}/master.png"],
             "prompt": "Use your built-in image_gen tool. " + STYLE_REF +
             "Character: Seo Jeonghun, a 47-year-old Korean civil engineer at a dam construction project. Tall, slightly "
             "hunched, short black hair with a few gray strands, light stubble, tired but kind eyes behind thin "
             "rectangular glasses. He wears a light-gray work shirt with sleeves rolled up under a navy safety vest with "
             "reflective silver stripes and a clipped ID badge, dark work trousers; one hand holds a rolled-up blueprint, "
             "the other hangs relaxed. " + FRAME})

out = ROOT / "art_work" / "jobs_chars_phase1.json"
out.write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(jobs), "jobs ->", out)
