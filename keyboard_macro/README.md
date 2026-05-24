# Keyboard Macro Planner

이 프로젝트는 **키보드 매크로 실행기**의 초기 GUI 버전입니다.

## 1) 기술 선택

### 권장안 (초기 버전)
- **Python + PySide6(Qt for Python)**
  - 이유: GUI 제작 속도 빠름, 프로토타입에 적합, 크로스 플랫폼 지원.
- **입력 시뮬레이션**: macOS는 Quartz 직접 이벤트, 그 외 OS는 `pynput`
- **실행 엔진**: `QTimer` + 별도 Worker Thread (`QThread`)

### 대안 (성능/안정성 중심)
- **C# + WPF / WinUI**
  - Windows 자동화/배포 친화성 우수.
- **Rust + Tauri + native hook crate**
  - 성능/안정성/경량 배포 강점, 초기 개발 난이도는 높음.

> 현재 요청(빠른 초기버전 + 추후 고도화) 기준으로는 **Python + PySide6**가 가장 효율적입니다.

---

## 2) 현재 기능 범위 (v0.1)

1. 키 입력 액션 등록
   - 일반 키 (예: A, S, D)
   - 방향키 (LEFT, RIGHT, UP, DOWN)
2. 타이머 기반 시퀀스 실행
   - 예) LEFT 5초 + X키 동시 입력
   - 다음) RIGHT 5초 + X키 동시 입력
3. Start / Stop / Emergency Stop
4. 시퀀스 목록 UI
   - 추가/복제/삭제/순서 변경
   - 선택한 스텝 편집
   - 테이블 셀 직접 편집
5. Config JSON 저장/불러오기
   - `Name`, `Loop/Count`, `Delay`, `Target`, 전체 스텝 저장
6. 실행 로그 뷰
7. 시작 지연 설정
   - Start를 누른 뒤 대상 창으로 포커스를 옮길 시간을 확보
8. 대상 앱 자동 활성화
   - macOS에서 `Target` 앱을 앞으로 올린 뒤 실행
9. 기본 키 녹화
   - macOS에서는 전역 키 이벤트를 잡아 대상 앱에 포커스가 있어도 스텝으로 추가
   - 전역 녹화가 막히면 앱 창에 포커스가 있는 상태의 키 입력을 스텝으로 추가
   - 키 down/up 시간과 hold 시간을 실행 로그에 기록
   - `Esc` 또는 `Stop Recording`으로 녹화 종료

---

## 3) 데이터 모델 설계

### ActionStep
- `id: str`
- `direction_key: str | None` (LEFT/RIGHT/UP/DOWN)
- `tap_keys: list[str]` (동시에 눌러줄 키 목록)
- `hold_seconds: float` (예: 5.0)
- `tap_interval_ms: int` (동시 키 반복 입력 간격, 예: 200)

### MacroSequence
- `name: str`
- `steps: list[ActionStep]`
- `loop: bool`
- `loop_count: int | None` (`None`이면 무한)

---

## 4) 동작 규칙

- 스텝 시작 시:
  1) 방향키 `keyDown`
  2) `hold_seconds` 동안 `tap_keys`를 interval마다 tap
  3) 종료 시 방향키 `keyUp`
- Stop 시:
  - 현재 눌린 키를 안전하게 모두 해제 후 종료
- UI 프리징 방지:
  - 실행은 Worker Thread에서 수행
  - UI는 Signal/Slot으로 상태 반영

---

## 5) 폴더 구조

```text
keyboard_macro/
  README.md
  requirements.txt
  src/
    main.py
    models.py
    macro_engine.py
```

---

## 6) 사용 방법

1. `./run_mac_linux.sh`로 실행합니다.
2. 기본 예제는 `LEFT + x 5초`, `RIGHT + x 5초`입니다.
3. `Target`을 확인합니다. 기본값은 `MapleStory Worlds`입니다.
4. `Delay`를 확인합니다. 기본 3초입니다.
5. `Start`를 누르면 macOS에서 `Target` 앱을 앞으로 올린 뒤 실행합니다.
6. `Target`을 비워두면 직접 대상 앱/창으로 포커스를 옮겨야 합니다.
7. 중단하려면 앱의 `Stop` 또는 `Emergency Stop`을 누릅니다.
8. 키 입력을 기록하려면 `Record`를 누르고 대상 앱에서 입력 후 `Esc`를 누릅니다.
9. 실제 입력이 안 들어가면 `Permission`을 눌러 접근성 권한 상태를 확인합니다.
10. `Test Input`은 지연 시간 후 `a`를 한 번 입력합니다. TextEdit/메모 같은 텍스트 입력칸에서 먼저 확인할 때 사용합니다.
11. 현재 화면 설정을 보관하려면 `Save Config`를 누릅니다.
12. 저장한 설정을 다시 쓰려면 `Load Config`를 누릅니다.

키 목록은 쉼표로 입력합니다.

```text
x
x, space
enter
left
f1
```

쉼표는 순차 입력입니다. 예를 들어 `1, space`는 `1`을 누른 뒤 `space`를 누릅니다.
동시 입력은 `+`로 묶습니다. 예를 들어 `shift+a` 또는 `cmd+s`처럼 입력합니다.
게임 입력 안정성을 위해 `Tap interval`은 최소 80ms로 보정됩니다. `space`처럼 씹히기 쉬운 키는 `1, space`처럼 순차 입력으로 두고 interval을 150-250ms부터 확인하는 편이 안정적입니다.

오른쪽 `Tap keys` 입력칸은 입력 즉시 선택된 스텝에 반영됩니다. 왼쪽 테이블 셀을 더블클릭해서 직접 수정할 수도 있습니다.

macOS에서 실제 입력이 안 들어가면 시스템 설정에서 Terminal 또는 Python에 접근성 권한을 허용해야 합니다.

## 7) 다음 단계

1. 전역 핫키(Start/Stop)
2. 녹화 모드 고도화(동시 입력/조합 입력)
3. 프리셋 관리
4. 예외 상황 대응 강화(포커스 변경, 입력 실패, 권한 문제)

---

## 8) 주의사항

- 게임/보안프로그램 대상 자동입력은 차단될 수 있습니다.
- OS별 권한(접근성/관리자 권한)이 필요할 수 있습니다.


## 9) 실행 방법 (클릭 실행 포함)

### Windows (클릭 실행)
1. `keyboard_macro/run_windows.bat` 더블클릭
2. 자동으로 가상환경 생성/의존성 설치 후 GUI 실행

### macOS/Linux
```bash
cd keyboard_macro
./run_mac_linux.sh
```

### 수동 실행(공통)
```bash
cd keyboard_macro
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_app.py
```
