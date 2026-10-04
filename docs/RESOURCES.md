# 리소스 규칙과 교체 방법

모든 리소스는 **ID(파일 이름)** 로 연결됩니다. 스크립트(`story/*.vn`)는 ID만 알고, 파일 경로·포맷·루프 지점은 매니페스트(`public/data/*.json`)가 담습니다. 같은 ID로 원본을 바꾸고 빌드 명령을 다시 돌리면 스크립트 수정 없이 교체됩니다.

## 한눈에 보기

| 종류 | 원본 (여기만 편집) | 설정 | 빌드 명령 | 게임용 출력 |
|---|---|---|---|---|
| 캐릭터 정보 | — | `story/characters.json` | `npm run assets` | `assets.json` `charConf` |
| 스프라이트 | `art_src/chars/<id>/` | `characters.json` → `sprite` | `python tools/img/build_sprites.py <id> --preview` | `public/assets/chars/<id>/`, `chars.json` |
| 배경 | `art_src/bg/<id>.png\|jpg\|webp` | — | `python tools/img/export_images.py` | `public/assets/bg/<id>.webp` |
| 이벤트 CG | `art_src/cg/<id>.png\|jpg\|webp` | `art_src/cg/titles.json` (갤러리 제목) | `python tools/img/export_images.py` | `public/assets/cg/`, 썸네일 |
| 음성 (TTS) | `voice/refs/<id>.wav` + `.txt` | `characters.json` → `tts` | `python tools/voice/make_voices.py gen` 후 `build` | `public/audio/voice/`, `voice.json`, `lipsync.json` |
| BGM | 생성 세션 폴더 또는 임의 오디오 파일 | `tools/music/bgm_select.json` | `python tools/music/make_loops.py <id>` | `public/audio/bgm/<id>.ogg`, `bgm.json` |
| 환경음·효과음 | `tools/sfx/synth.py` (절차 합성) | 같은 파일 | `python tools/sfx/synth.py` | `public/audio/amb`, `se`, `sfx.json` |
| 크레디트 | — | `story/credits.json` | `npm run assets` | `assets.json` `credits` |

마지막에는 항상 `npm run build`를 실행합니다(`assets` → `story --strict-assets` → `typecheck` → `vite build`). 스크립트가 없는 ID나 표정·포즈를 참조하면 컴파일이 실패하므로, 빠진 리소스가 있으면 빌드 단계에서 드러납니다.

## 공통 규칙

- ID는 영문 소문자, 숫자, `_`만 씁니다(`bcroom_storm`, `cg_true_end`). 스크립트에서 쓰는 ID를 바꾸면 `.vn`의 참조도 함께 바꿔야 합니다.
- `art_src/`, `voice/refs/`, 음악 세션 폴더가 원본입니다. `public/`의 파일은 빌드 결과물이므로 직접 편집하지 않습니다.
- 교체 전 원본은 `art_work/replaced/`로 옮겨 보관합니다(예: `cg_dawn_v1.png`). 같은 폴더에 `_v2` 같은 사본을 두지 않습니다. 파일 이름이 곧 ID이기 때문에 사본이 새 리소스로 등록됩니다.
- 새 외부 리소스를 들이면 라이선스를 확인하고 `story/credits.json`에 출처를 적습니다.

## 캐릭터 (`story/characters.json`)

키는 스크립트에서 쓰는 화자 이름입니다(`윤슬: 대사`). 캐릭터 한 명의 설정은 모두 이 한 곳에 있습니다.

```json
"윤슬": {
  "id": "yunseul", "name": "윤슬", "color": "#ffb36b",
  "voice": true, "voicePrefix": "ys",
  "tts": { "ref": "voice/refs/yunseul.wav", "refText": "voice/refs/yunseul.txt" },
  "sprite": {
    "scale": 0.84, "y": 38, "defaultPose": "uniform_a",
    "bodies": { "uniform_a": "body/uniform_a.png" },
    "exprs": ["neutral", "smile"],
    "noblink": ["laugh"],
    "headBox": [360, 120, 700, 460],
    "eyesBox": [362, 248, 572, 352]
  }
}
```

- `voicePrefix`: 음성 ID의 접두사입니다(`#ys0001`). 컴파일러가 새 대사에 자동으로 번호를 붙입니다. 이미 붙은 ID는 바꾸지 않습니다.
- `sprite`가 없으면 이름만 나오는 인물이고, `tts`가 없으면 음성이 없습니다.
- `scale`과 `y`는 1920×1080 무대 기준 표시 크기와 세로 오프셋(px)입니다.
- `eyesBox`(선택)는 눈 영역을 자동으로 못 찾을 때 직접 지정하는 값입니다.

## 스프라이트 (`art_src/chars/<id>/`)

```
master.png                 기본 몸 + 무표정(neutral), 투명 배경
body/<pose>.png            다른 옷·포즈 (머리 위치는 master와 동일해야 함)
expr/<expr>.png            표정 (neutral 제외)
var/<expr>_blink.png       눈 감은 버전 (noblink 표정은 생략)
var/<expr>_m1.png          입 조금 벌림
var/<expr>_m2.png          입 크게 벌림
```

- 모든 이미지는 **같은 캔버스 크기와 같은 머리 위치**여야 합니다. 빌더가 ECC로 정렬하지만, 원본끼리 몇 픽셀 이상 어긋나면 합성 경계가 보입니다. 이미지 편집 AI로 만들 때는 "얼굴·머리 위치, 캔버스, 크롭은 그대로 두고 X만 바꿔라"로 지시합니다.
- 얼굴 레이어는 모든 몸에 공용으로 올라갑니다. 옷깃 모양이 다른 몸(예: 셔츠 → 티셔츠)은 빌더가 알아서 가려 주지만, 목선이 크게 다르면 결과를 확인해야 합니다.
- 빌드 결과 확인:
  - 로그의 `ecc` 값이 0.95 미만이면 `low-correlation`으로 표시됩니다. 이 경우 원본 정렬을 다시 확인합니다.
  - `art_work/sprites/preview_<id>.jpg`, `detail_<id>.jpg`에서 눈 깜빡임·입 모양·경계선을 봅니다.
- 캐릭터 추가 순서:
  1. `characters.json`에 `sprite` 블록을 추가합니다.
  2. 위 규칙대로 원본 이미지를 넣습니다.
  3. `build_sprites.py <id> --preview`를 실행합니다.
  4. `npm run build`를 실행합니다.

## 배경·CG

- 원본은 3:2 비율(예: 1536×1024) 이상이어야 합니다. 1920×1280 WebP로 변환되고, 화면에는 가운데 16:9가 보입니다.
- 교체는 같은 이름으로 덮어쓰고 `export_images.py`를 실행하면 됩니다. 원본이 WebP보다 새로우면 다시 변환합니다.
- CG 갤러리 제목은 `art_src/cg/titles.json`에서 관리합니다. 목록에 없으면 ID가 그대로 표시됩니다.
- 날씨 효과는 이미지가 아니라 스크립트에서 지정합니다: `@scene <bg> weather=storm:0.9`
  - 실내 장면에는 `rain`이나 `storm`을 쓰지 말고 `lightning`(번쩍임과 천둥만)을 씁니다.
  - `@scene`을 실행하면 이전 날씨는 지워집니다.
  - CG가 떠 있는 동안에는 `rain`, `storm`, `glitter`가 자동으로 가려집니다.

## 음성 (TTS)

- 대사 원문은 `.vn`에 있고, 컴파일러가 `voice/lines.json`을 만듭니다. `<...>` 안의 연기 지시는 TTS에만 전달되고 화면에는 나오지 않습니다.
- 목소리 교체:
  1. `voice/refs/<id>.wav`(깨끗한 단독 음성 10~20초)와 `.txt`(그 음성의 정확한 대본)를 바꿉니다.
  2. `python tools/voice/make_voices.py gen --chars <id>`를 실행합니다. 참조 음성의 지문(hash)이 바뀌면 그 캐릭터의 대사가 전부 다시 생성됩니다.
  3. `python tools/voice/make_voices.py build`를 실행합니다. 음성, 립싱크, 매니페스트가 함께 갱신됩니다.
  4. `npm run build`를 실행합니다.
- 대사 문구를 고치면 해당 줄만 다시 생성됩니다(텍스트 hash로 판단).
- 생성한 음성은 Whisper로 다시 받아 적어 대조합니다. 불합격이면 최대 3번까지 재시도합니다.
  - 인식기 오판(연음, 길게 늘인 소리)이라 판단되면 들어 보고 `make_voices.py accept --only <voice id>`로 수동 통과시킵니다.
- 실제 인물이나 성우의 목소리를 참조 음성으로 쓰지 않습니다. 지금의 참조 음성은 모두 참조 없이 생성한 합성 화자입니다.
- 립싱크는 음성 파형에서 자동으로 계산합니다. 입 모양 기준값은 `src/engine/sprite.ts`에 있습니다(m2 > 0.56, m1 > 0.26).

## BGM (`tools/music/bgm_select.json`)

키가 스크립트의 `@bgm <id>`입니다.

```json
"lake": { "dir": "12b_lake", "stem": "no_vocals", "loop": true, "title": "호수의 윤슬", "min_body": 90 },
"lake": { "file": "audio_src/bgm/lake.wav", "loop": true, "loopStart": 12.5, "loopEnd": 98.0, "title": "호수의 윤슬" }
```

- 소스는 둘 중 하나입니다.
  - `dir` + `stem`: 생성 세션(`music-20260930-200500/<dir>`)의 트랙입니다. `no_vocals`는 Demucs 반주 스템, `source`는 원본 믹스입니다.
  - `file`: 직접 준비한 wav/flac/ogg입니다. 교체용으로 쓰며, 원본은 `audio_src/bgm/`에 둡니다.
- 루프 방식은 셋 중 하나입니다.
  - 루프 지점을 자동으로 찾기: 기본값입니다. `min_body`는 루프 구간의 최소 길이(초)입니다.
  - 수동 지정: `loopStart`/`loopEnd`(초)를 적습니다.
  - 곡 전체 반복: `"mode": "full"`로 곡을 끝까지 재생한 뒤 처음부터 다시 틉니다.
- 음량은 `lufs`로 맞춥니다. 기본은 -18이고, 엔딩 테마는 -16입니다.
- 이음새 확인용 이미지가 `art_work/loops/<id>_seam.png`에 생깁니다. 그래도 최종 판단은 반드시 귀로 합니다.
- 제작 규칙:
  - 게임 BGM에는 가사나 보컬이 없어야 합니다.
  - YuE2는 "instrumental"로 요청해도 보컬을 넣는 경우가 있습니다. 그래서 반주 스템을 쓰고, `separate.py`, `stem_words.py`로 보컬이 남았는지 검사합니다.
  - 루프 구간 안에 곡의 끝부분(페이드아웃)이 들어가면 안 됩니다.

### 알려진 문제 (재검증 필요, 아직 손대지 않음)

- `lastbroadcast`(10)와 `silence`(11)는 곡 중간에 보컬 잔향이 들린다는 보고가 있습니다. 둘 다 `mode: full`이라 곡 전체가 반복되므로, 곡 전체를 들어 봐야 합니다.
- 일부 트랙은 생성 단계부터 의도와 다르게 나왔습니다. 첫 요청은 instrumental이었는데 보컬이 섞였고, v2~v4 재생성분이 섞여 있습니다. 모든 BGM을 한 번씩 끝까지 청취해서 재검증하고, 필요하면 `file` 방식으로 교체하는 것을 권장합니다.

## 교체 후 검증

개발 서버(`npx vite`, 포트 47813)를 켠 상태에서 실행합니다.

```powershell
npm run build                                   # 참조 누락이면 여기서 실패
python tools/qa/route_check.py                  # 에셋 디코딩 + 대표 선택 9가지 + 명령 커버리지
python tools/qa/route_check.py --all            # 216가지 선택 전부 (오래 걸림; --first/--part로 나눠 실행 가능)
python tools/qa/fx_check.py                     # 장면별 날씨 상태
python tools/qa/tour.py <stop ...>              # 주요 장면 실제 화면 캡처 → art_work/qa/tour/
python tools/qa/lipsync_probe.py ys0030 ...     # 음성 교체 후 립싱크 일치율
python tools/qa/playtime.py                     # 예상 플레이타임
```
