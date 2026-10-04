"""Emit background + event CG jobs (landscape 1536x1024)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BG_STYLE = ("Use your built-in image_gen tool to create one image. Anime background art for a visual novel: "
            "high-quality 2D Japanese animation film style, painterly and highly detailed, clean shapes, vivid but "
            "natural colors, soft atmospheric perspective, crisp light and shadow. Setting: Sorisil, a small remote "
            "mountain village in Chungcheong province, South Korea, during the last summer before it is flooded by a "
            "new dam. Landscape canvas at the largest landscape size (1536x1024), eye-level camera, keep the lower "
            "middle of the frame fairly uncluttered so characters can stand there. Absolutely no people, no animals "
            "in the foreground, no text, no letters, no numbers, no writing on signs or banners, no watermark. Scene: ")

BGS = {
    "busstop_day": "a tiny rural bus stop at the entrance of the village: a weathered concrete bus shelter with a faded "
                   "blue wooden bench and a rusty blank timetable board, a narrow asphalt road curving down into a "
                   "green valley, a long plain white cloth banner stretched between two wooden poles, electric poles "
                   "and sagging wires, lush hills, towering cumulonimbus clouds, bright midday summer sun.",
    "busstop_evening": "the same tiny rural bus stop at the village entrance at dusk: weathered concrete shelter with a "
                       "blue bench, the road curving into the valley, a plain white cloth banner between poles, "
                       "electric wires, the sky glowing orange and lavender after sunset, the first streetlight on, "
                       "melancholic end-of-summer mood.",
    "village_day": "a narrow village lane lined with low mossy stone walls and old one-story houses with slate and "
                   "traditional tile roofs, pumpkin vines climbing the walls, a persimmon tree, earthenware sauce jars "
                   "in a yard, electric poles, green mountains behind, sunny summer afternoon.",
    "village_evening": "the same narrow village lane with stone walls and old slate and tile roofs at golden hour, long "
                       "warm shadows, the sky turning orange and pink, a few windows lit, cooking smoke rising from a "
                       "chimney, nostalgic mood.",
    "store_day": "the front of a tiny old village general store: a one-story building with wooden-framed glass sliding "
                 "doors, a faded striped awning, a blank signboard, a glass-door drink cooler, stacked plastic crates, "
                 "a low wooden outdoor platform bench with a small electric fan and a red plastic chair, potted plants, "
                 "summer afternoon light.",
    "store_night": "inside a tiny old village general store at night: narrow aisles of shelves with snacks, instant "
                   "noodles and daily goods in plain packaging without any text, a small counter with an old cash box "
                   "and a portable radio, a single warm bulb, a sliding glass door showing the dark summer night.",
    "room_night": "a small rented room in an old village house where a boy stays temporarily: yellow laminated floor, "
                  "a thin folded mattress, unopened cardboard moving boxes, an electric fan, a low desk with a small "
                  "portable radio, a window with a mosquito screen open to the dark summer night, warm lamp light.",
    "room_day": "the same small rented room in soft morning light: yellow laminated floor, a folded mattress, cardboard "
                "moving boxes, an electric fan, a low desk with a small portable radio, a window with a mosquito screen "
                "showing green trees and blue sky.",
    "stream_day": "a crystal-clear mountain stream with smooth round boulders and shallow rapids, dappled sunlight "
                  "through lush green trees, a large flat rock by the water, sparkling water surface, deep summer.",
    "stream_night": "the same mountain stream at night: deep blue moonlight, dark silhouettes of trees, softly glowing "
                    "fireflies scattered in the air above the water, gentle reflections, magical and quiet.",
    "school_day": "an abandoned small rural branch elementary school: a two-story weathered white concrete building "
                  "with faded paint and a stopped clock, a dirt schoolyard with a rusty swing and a tall zelkova tree, "
                  "a homemade radio antenna mast on the roof, grass growing through cracks, deep blue summer sky.",
    "school_night": "the same abandoned rural school at night under a starry sky: one second-floor window glowing warm "
                    "yellow, a homemade antenna mast on the roof with a small red light, the dark schoolyard and the "
                    "zelkova tree silhouette.",
    "bcroom_night": "inside an old school broadcasting room at night: a wooden desk with a vintage mixing console, a "
                    "studio microphone on a boom arm, two cassette decks and a reel-to-reel tape recorder, stacks of "
                    "cassette tapes with blank labels, egg-crate acoustic foam on the walls, a corkboard with a "
                    "hand-drawn village map full of colorful pins, a warm desk lamp, a window showing the night sky.",
    "bcroom_day": "the same old school broadcasting room in the afternoon: a wooden desk with a vintage mixing console, "
                  "a studio microphone on a boom arm, cassette decks and a reel-to-reel recorder, stacks of cassette "
                  "tapes with blank labels, egg-crate foam on the walls, a corkboard with a hand-drawn map full of pins, "
                  "sunbeams with floating dust through the window.",
    "tree_day": "a giant old zelkova tree with a wooden pavilion beneath it in the middle of the village, rice paddies "
                "spreading behind, heat haze shimmering, a quiet sleepy summer noon.",
    "echo_sunset": "a rocky mountain ledge high above a deep green valley, the tiny village far below and a river "
                   "winding through it, layered mountain ridges fading into the distance, a dramatic orange and violet "
                   "sunset sky.",
    "path_night": "a narrow country path between rice paddies at night under a dazzling starry sky with the Milky Way, "
                  "a single old streetlight, the dark silhouettes of mountains, a few fireflies.",
    "hall_day": "inside a village community hall: a wide room with a laminated floor, rows of folding chairs, a blank "
                "projector screen at the front, a long table with microphones and water bottles, fluorescent lights, "
                "summer daylight through the windows.",
    "demolish_day": "part of the village being demolished: half-torn-down houses, piles of rubble and broken roof tiles, "
                    "a parked excavator, a chain-link fence, a lone persimmon tree still standing, dusty harsh "
                    "afternoon light, melancholic.",
    "storm_night": "the village in a violent typhoon at night: sheets of slanting rain, trees bending in the wind, a "
                   "swollen muddy stream overflowing its banks, flickering streetlights, the abandoned school on a hill "
                   "in the distance, dark blue-gray tones, lightning glowing inside the clouds.",
    "dam_day": "a huge dam under construction at the end of the valley: tall concrete walls, tower cranes, construction "
               "machinery, a site office made of containers, safety fences, summer haze.",
    "ceremony_day": "the schoolyard of the abandoned school prepared for a farewell hometown ceremony: a white event "
                    "tent with folding chairs, strings of small plain triangular flags, display boards with old photos "
                    "(blurry, no text), a small stage with a microphone stand, late afternoon golden light.",
    "lake_day": "four years later: a vast calm dam lake filling the valley where the village used to be, green mountains "
                "around it, sunlight glittering on the water surface like countless diamonds, a wooden observation deck "
                "at the shore, high summer.",
    "city_night": "view from a small apartment room in a big Korean city at night: a window with city lights and "
                  "apartment towers, a desk with a laptop and a small portable radio, a warm desk lamp, lonely mood.",
}

YS_DESC = ("The girl is Ha Yunseul exactly as in the first attached reference image: shoulder-length dark navy-black "
           "wavy hair with side-swept bangs, a thin braid on her left side tied with a small red string, warm "
           "amber-brown eyes, orange retro over-ear headphones with a coiled black cable. ")
UNIFORM = "She wears her summer school uniform: white short-sleeve blouse, loose red ribbon tie, knee-length dark teal pleated skirt. "
CASUAL = ("She wears her casual summer outfit: an oversized faded light-blue chambray shirt worn open over a white "
          "T-shirt, and dark denim shorts. ")
CG_STYLE = ("Use your built-in image_gen tool to create one image: an event CG illustration for a visual novel, in "
            "exactly the art style of the attached reference image (high-quality 2D Japanese anime illustration, clean "
            "lineart, soft cel shading), cinematic composition, expressive lighting, detailed background. Landscape "
            "canvas at the largest landscape size (1536x1024). No text, no letters, no watermark. ")
Y_REF = "art_src/chars/yunseul/master.png"

CGS = {
    "cg_meet": ([Y_REF], YS_DESC + UNIFORM +
                "Bright summer afternoon at a crystal-clear mountain stream: she crouches on a flat rock holding a small "
                "silver handheld voice recorder out toward the rushing water, wearing the headphones on her ears, and "
                "looks up at the viewer with her index finger pressed to her lips in a 'shh!' gesture and a sharp, "
                "mischievous glare. Sunlight sparkles on the water. The viewer stands on the bank above her."),
    "cg_broadcast": ([Y_REF], YS_DESC + CASUAL +
                     "Night inside an old school broadcasting room: she sits at a vintage mixing console wearing the "
                     "orange headphones over her ears, leaning toward a studio microphone on a boom arm and speaking "
                     "with a confident, playful smile, one hand on a fader. Warm desk lamp light, glowing VU meters, "
                     "stacks of cassette tapes with blank labels, egg-crate foam, a dark window with stars."),
    "cg_echo": ([Y_REF], YS_DESC + UNIFORM +
                "Sunset on a rocky mountain ledge high above a valley: she cups her hands around her mouth and shouts "
                "toward the distant mountains, hair, braid and ribbon blowing in the wind, seen from a slight "
                "side-back angle, a huge orange and violet sunset sky, the tiny village far below."),
    "cg_tape_repair": ([Y_REF], YS_DESC + UNIFORM +
                       "Close-up at a wooden desk in the school broadcasting room in afternoon light: a boy's hands "
                       "(only his hands and forearms are visible, white short sleeves) carefully rewind the loose "
                       "magnetic tape of an old cassette with a hexagonal pencil, while she leans in very close beside "
                       "him, chin on her hand, watching intently with wide curious eyes. Small screwdrivers and a "
                       "soldering iron on the desk, dust motes in the sunbeam."),
    "cg_bongsun_radio": (["art_src/chars/bongsun/master.png"],
                         "The character is Kim Bongsun exactly as in the attached reference image (a 78-year-old Korean "
                         "grandmother with short permed gray hair, pink floral blouse, white apron). Night inside her "
                         "tiny old village store: she sits on a low stool hugging a small old portable radio to her "
                         "chest with both arms, eyes closed, tears streaming down her wrinkled cheeks with a trembling "
                         "smile. A single warm bulb, shelves of goods in plain packaging without text, a sliding glass "
                         "door showing the dark night."),
    "cg_fireflies": ([Y_REF], YS_DESC + CASUAL +
                     "Summer night at a mountain stream: she stands barefoot in ankle-deep water surrounded by hundreds "
                     "of softly glowing fireflies, turning back toward the viewer with a gentle, slightly shy smile, "
                     "the headphones around her neck. Moonlight and firefly glow reflect on the water, dreamy bokeh."),
    "cg_storm": ([Y_REF], YS_DESC + CASUAL +
                 "Blackout during a typhoon night inside the school broadcasting room: her hair is wet, she wears the "
                 "orange headphones and grips a microphone with both hands, speaking urgently with determined, "
                 "tearful eyes, lit only by a battery camping lantern and the red glow of a small transmitter. Rain "
                 "streams down the window behind her with a flash of lightning; cables and car batteries on the floor."),
    "cg_dawn": ([Y_REF], YS_DESC + CASUAL +
                "Early dawn after the storm inside the school broadcasting room: she sleeps peacefully, leaning her head "
                "on the shoulder of a boy who sits next to her on the floor against the wall (the boy is seen from the "
                "side with his face mostly out of frame, dark hair, white T-shirt). Her headphones are askew, a thin "
                "blanket over her knees, pale golden morning light through the rain-streaked window, a microphone and "
                "a switched-off lantern nearby. Tranquil."),
    "cg_mother_tape": ([Y_REF], YS_DESC + UNIFORM +
                       "Sunset inside the school broadcasting room: she sits alone on a chair hugging her knees, "
                       "wearing the orange headphones plugged into an old cassette player on the desk, eyes closed, "
                       "tears running down her cheeks with a small bittersweet smile. Orange sunset light streams "
                       "across the room; an open cassette case lies on the desk."),
    "cg_last_broadcast": ([Y_REF], YS_DESC + UNIFORM +
                          "Dusk, the last broadcast: she stands at the studio microphone in the school broadcasting "
                          "room decorated with warm string lights, headphones on, speaking with a trembling smile while "
                          "tears fall. Through the window behind her, villagers holding small lanterns gather in the "
                          "schoolyard below under a deep blue and orange dusk sky. Bittersweet and luminous."),
    "cg_true_end": ([Y_REF],
                    "The girl from the attached reference image, Ha Yunseul, four years later at 21: slightly more "
                    "mature face, dark navy-black wavy hair a little longer with the same thin braid tied with a small "
                    "red string, amber-brown eyes, the same orange retro headphones around her neck. She wears a white "
                    "summer blouse and a long light-blue skirt. Bright summer day at the shore of a vast dam lake "
                    "glittering with sunlight: she turns around toward the viewer with a radiant, tearful smile, wind "
                    "in her hair, the sparkling lake and green mountains behind her."),
    "cg_normal_end": ([Y_REF],
                      "No people. Late night in a small city apartment: a desk by the window with a small portable "
                      "radio glowing softly, next to it an old cassette tape tied with a thin red string, city lights "
                      "blurred beyond the glass, raindrops on the window. Lonely and bittersweet. Use the reference "
                      "image only for the art style."),
    "cg_father_album": (["art_src/chars/father/master.png"],
                        "The man is Seo Jeonghun exactly as in the attached reference image (47, short black hair with "
                        "a little gray, thin rectangular glasses, light stubble), wearing a plain gray T-shirt. Night "
                        "in a small rented room lit by a desk lamp: he sits cross-legged on the floor with a thick open "
                        "photo album full of old photographs of rural villages, looking down at it with a gentle, sad "
                        "smile; cardboard moving boxes behind him."),
    "cg_title": ([Y_REF], YS_DESC + UNIFORM +
                 "Key visual: she stands on the rooftop of an abandoned rural school next to a homemade radio antenna "
                 "mast, the orange headphones around her neck, holding a small silver voice recorder, hair and skirt "
                 "blown by the wind, looking back over her shoulder at the viewer with a faint smile. Behind her an "
                 "enormous summer sky with towering cumulonimbus clouds, a green valley with a small village below, "
                 "and far away at the end of the valley a concrete dam. Place her in the right half of the image and "
                 "keep the left third as open sky for a title logo."),
}

jobs = []
for k, desc in BGS.items():
    jobs.append({"id": f"bg_{k}", "out": f"art_src/bg/{k}.png", "images": [], "prompt": BG_STYLE + desc})
for k, (refs, desc) in CGS.items():
    jobs.append({"id": k, "out": f"art_src/cg/{k}.png", "images": refs, "prompt": CG_STYLE + desc})
out = ROOT / "art_work" / "jobs_bg_cg.json"
out.write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(jobs), "jobs ->", out)
