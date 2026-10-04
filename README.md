<div align="center">

# 여름이 가라앉기 전에
### Before the Summer Sinks

댐 건설로 물에 잠길 산골 마을의 마지막 여름.<br>
전학생 한결과 해적 라디오 DJ 윤슬이 마을의 소리 백 개를 모으는 한국어 비주얼 노벨.

![Platform](https://img.shields.io/badge/platform-Windows%20x64-0078D6?logo=windows)
![Electron](https://img.shields.io/badge/Electron-44.5-47848F?logo=electron&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-7.0-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8.3-646CFF?logo=vite&logoColor=white)
![Language](https://img.shields.io/badge/언어-한국어-e05d44)
![Playtime](https://img.shields.io/badge/플레이타임-약%2065~90분-f0a030)
![Endings](https://img.shields.io/badge/엔딩-2종-8a63d2)

<img src="docs/media/title.jpg" width="880" alt="타이틀 화면">

</div>

## 소개

일곱 번 이사하는 동안 "정 붙이지 않기"를 규칙으로 삼아 온 서한결은, 수몰 예정지인 충청도 산골 마을 **소리실**로 전학 온다. 그곳에서 폐교된 분교 방송실에 숨어 불법 심야 라디오 **88.3MHz**를 송출하는 하윤슬을 만난다. 마을이 물에 잠기기까지 남은 사십 일, 두 사람은 사라질 마을의 소리 백 개를 녹음하기로 한다.

- 프롤로그 + 7개 장 + 엔딩, 선택지 6개, 엔딩 2종 (트루 「윤슬」 / 노멀 「잔향」)
- 한 회차 약 65~90분 (읽는 속도에 따라)
- 대사 약 870줄, 음성 398개 (약 32분 분량)
- 오리지널 일본 애니메이션풍 2D 아트: 배경 25장, 이벤트 CG 14장, 레이어 스프라이트 3명

## 스크린샷

<table>
  <tr>
    <td><img src="docs/media/scene_stream.jpg" alt="개울에서 만난 윤슬"></td>
    <td><img src="docs/media/scene_store.jpg" alt="봉순 할머니의 가게"></td>
  </tr>
  <tr>
    <td><img src="docs/media/scene_bcroom.jpg" alt="분교 방송실"></td>
    <td><img src="docs/media/scene_father.jpg" alt="아버지와의 밤"></td>
  </tr>
  <tr>
    <td><img src="docs/media/cg_fireflies.jpg" alt="이벤트 CG: 반딧불 개울"></td>
    <td><img src="docs/media/cg_storm.jpg" alt="이벤트 CG: 태풍의 밤"></td>
  </tr>
  <tr>
    <td><img src="docs/media/scene_storm_room.jpg" alt="정전된 태풍의 밤 방송실"></td>
    <td><img src="docs/media/cg_true_end.jpg" alt="이벤트 CG: 트루 엔딩"></td>
  </tr>
</table>

## 연출

<table>
  <tr>
    <th>음성 기반 립싱크</th>
    <th>태풍 (비 · 번개 · 천둥)</th>
    <th>반딧불</th>
  </tr>
  <tr>
    <td align="center"><img src="docs/media/lipsync.gif" width="240" alt="립싱크"></td>
    <td align="center"><img src="docs/media/storm.gif" width="400" alt="태풍 효과"></td>
    <td align="center"><img src="docs/media/fireflies.gif" width="400" alt="반딧불 효과"></td>
  </tr>
</table>

- **립싱크**: 실제 음성 파형에서 50fps 입 모양 곡선을 뽑습니다(음량 + 제1포먼트 대역 비율). 재생 중인 오디오 시계에 맞춰 입을 세 단계(닫힘/조금/크게)로 바꾸고, 눈 깜빡임은 따로 돌아갑니다.
- **날씨·빛**: 캔버스 파티클(비, 폭풍, 반딧불, 먼지, 물반짝임, 잡음)과 장면 조명(낮·노을·밤·램프·정전)을 씁니다. 실내 장면에서는 창밖 번개만 번쩍이고, CG가 뜨면 배경 쪽 날씨는 가려집니다.
- **음성 효과**: 라디오, 카세트테이프, 전화, 확성기, 메아리 필터를 대사마다 걸 수 있습니다.

## 시스템

<table>
  <tr>
    <td><img src="docs/media/choice.jpg" alt="선택지"></td>
    <td><img src="docs/media/backlog.jpg" alt="대사 기록"></td>
  </tr>
  <tr>
    <td><img src="docs/media/saveload.jpg" alt="저장하기"></td>
    <td><img src="docs/media/settings.jpg" alt="환경설정"></td>
  </tr>
  <tr>
    <td colspan="2" align="center"><img src="docs/media/gallery.jpg" width="640" alt="추억 (CG · 음악 · 엔딩 갤러리)"></td>
  </tr>
</table>

- 저장 36칸, 자동 저장(장 시작마다), 퀵 세이브/로드
- 대사 기록과 기록 속 음성 다시 듣기, 현재 대사 음성 다시 듣기
- 오토 모드, 스킵(읽은 대사만 / 전부)
- 음량 6종 개별 조절: 전체, 배경음악, 음성, 환경음, 효과음, 시스템음
- 텍스트 속도, 오토 속도, 대화창 투명도
- 전체화면/창 모드 전환과 창 크기 기억. 설정과 저장은 재실행 후에도 유지됩니다.
- 갤러리: 이벤트 CG, 음악 감상, 엔딩 목록

### 조작

| 입력 | 동작 |
|---|---|
| 클릭 / Enter / Space / ↓ / 휠 아래 | 다음 대사 |
| 휠 위 / ↑ / L | 대사 기록 |
| 우클릭 / Esc | 메뉴 (열린 창 닫기) |
| Ctrl (누르는 동안) / S | 스킵 |
| A | 오토 |
| H | 대화창 숨기기 |
| R | 음성 다시 듣기 |
| F5 / F9 | 퀵 세이브 / 퀵 로드 |
| F11 / Alt+Enter | 전체화면 |

## 실행

### 배포본

`release/SummerSinks-win32-x64/SummerSinks.exe`를 실행합니다. 설치할 필요는 없고, 폴더째 옮겨도 됩니다.

GitHub에서는 `v*` 태그를 푸시하면 `.github/workflows/release.yml`이 이 폴더를 ZIP으로 묶고 SHA-256 체크섬과 함께 GitHub Release에 첨부합니다. Actions에서 수동 실행하면 같은 ZIP을 workflow artifact로 받을 수 있습니다.

### 소스에서

Node.js 22.12 이상이 필요합니다(Vite 8 요구사항, 개발 환경은 v24.13). 에셋 파이프라인 도구를 쓰려면 Python 3.13과 ffmpeg도 필요합니다.

```powershell
npm install
npm run dev        # 브라우저 개발 서버 http://localhost:47813
npm run app        # dist/ 빌드를 Electron 창으로 실행
npm run build      # 에셋 매니페스트 → 스토리 컴파일(누락 검사) → 타입 검사 → vite build
npm run package    # build 후 release/SummerSinks-win32-x64 생성
```

## 구조

```
story/                 스크립트(.vn), 캐릭터 레지스트리(characters.json), 크레디트(credits.json)
src/engine/            VM, 스테이지, 스프라이트(립싱크), 오디오, 날씨 FX, 대화창, 저장
src/ui/                타이틀 · 메뉴 · 저장 · 설정 · 기록 · 갤러리 · 엔딩 화면
electron/              데스크톱 셸 (app:// 프로토콜, 창 API)
art_src/               이미지 원본 (배경, CG, 캐릭터 레이어 원본)
voice/refs/            캐릭터별 TTS 참조 음성
tools/                 에셋 파이프라인 (이미지 · 스프라이트 · 음성 · 음악 · 효과음 · QA)
public/                빌드된 게임 에셋과 매니페스트 (직접 편집하지 않음)
docs/RESOURCES.md      리소스 규칙과 교체 방법
```

엔진은 외부 VN 엔진 없이 TypeScript로 직접 만든 DOM 엔진입니다. 1920×1080 논리 무대를 쓰고, 어떤 창 크기에서도 레터박스로 맞춥니다. 스토리는 데이터 기반입니다.

```text
@scene bcroom_storm light=dark weather=lightning:0.6
@show yunseul casual_b surprised at=center
윤슬(surprised)<shocked, soaked, breathless>: 철새?! 너 미쳤어? 이 날씨에— #ys0205
```

- `@`로 시작하는 줄은 연출 명령입니다.
- `이름(표정)<연기 지시>: 대사` 형식에서 연기 지시는 TTS에만 전달됩니다.
- `#ys0205`는 음성 ID입니다. 컴파일러가 자동으로 붙입니다.
- 컴파일러(`tools/story/compile.mjs --strict-assets`)는 없는 배경·표정·포즈·음성을 참조하면 빌드를 멈춥니다.

## 리소스 제작 파이프라인

| 리소스 | 방식 |
|---|---|
| 캐릭터 · 배경 · CG | Codex CLI `image_gen`으로 생성합니다. 스프라이트는 기본 몸에서 편집해 만든 표정, 눈 감음, 입 2단계를 ECC로 정렬한 뒤 얼굴·눈·입 레이어로 분리합니다. |
| 음성 | Fish Audio TTS(`s2.1-pro`)로 캐릭터별 참조 음성을 복제해 만듭니다. 참조 음성은 실제 인물을 흉내 내지 않은 합성 화자입니다. 생성한 음성은 Whisper large-v3로 다시 받아 적어 대조하고, 틀리면 재생성합니다. |
| 배경음악 | 로컬 HOT-Step YuE2로 생성합니다. Demucs로 보컬을 분리해 반주만 쓰고, 루프 지점을 자동으로 찾아 크로스페이드를 넣습니다. 엔딩 테마는 보컬곡입니다. |
| 환경음 · 효과음 | 절차적 합성(`tools/sfx/synth.py`)으로 만들어 외부 샘플을 쓰지 않습니다. |
| 글꼴 | Gowun Batang, Gowun Dodum, Nanum Pen Script (SIL OFL) |

캐릭터, 음성, 배경, CG, 음악을 바꾸는 방법은 **[docs/RESOURCES.md](docs/RESOURCES.md)** 에 정리했습니다. 원본 파일을 같은 ID로 바꾸고 해당 빌드 스크립트를 다시 돌리면 스크립트를 고치지 않아도 반영됩니다.

## 품질 검증

실제 Chrome과 Electron에서 게임을 돌려 검증하는 스크립트가 `tools/qa/`에 있습니다.

| 스크립트 | 내용 |
|---|---|
| `route_check.py [--all]` | 오디오 463개·이미지 144개 디코딩, 선택지 조합 216개 전체 실행, 엔딩 도달과 변수 검증, 명령 커버리지 |
| `fx_check.py` | 장면별 날씨 상태와 저장/복원 |
| `lipsync_probe.py` | 재생 중인 음성과 입 모양의 프레임 단위 일치율 (현재 94~96%) |
| `tour.py` | 주요 장면 실제 화면 캡처 |
| `electron_check.py` | 패키지 앱의 로딩, 창 크기, 전체화면, 재실행 후 저장 유지 |
| `playtime.py` | 루트별 예상 플레이타임 |
| `readme_media.py` | 이 README의 스크린샷과 GIF 생성 |

## 알려진 문제

- 배경음악 일부(`lastbroadcast`, `silence`)에 보컬 잔향이 남아 있습니다. 생성 단계부터 의도와 다르게 나온 트랙도 있어 전곡 재검증이 필요합니다. 자세한 내용은 [RESOURCES.md](docs/RESOURCES.md#알려진-문제-재검증-필요-아직-손대지-않음)에 있습니다.
- 음성은 Fish Audio 무료 모델로 생성했습니다.

## 크레디트

시나리오 · 연출 · 프로그래밍: Kiro<br>
이미지: Codex image_gen 기반 생성 · 합성 · 음성: Fish Audio TTS · 음악: HOT-Step YuE2, Demucs<br>
글꼴: Gowun Batang, Gowun Dodum, Nanum Pen Script (SIL Open Font License)
