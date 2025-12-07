# Time Timer - macOS App

네이티브 macOS 타임 타이머 앱입니다. SwiftUI로 제작되었으며, 미니멀하고 프리미엄한 디자인을 제공합니다.

## 주요 기능

- ⏱️ **두 가지 타이머 모드**
  - 기본 카운트다운 타이머 (큰 숫자 표시 + 프로그레스 바)
  - 시각적 원형 타이머 (원형 프로그레스 링)

- 🔔 **알람/알림 기능**
  - 타이머 완료 시 macOS 네이티브 알림
  - 시스템 사운드 재생

- ⚡ **프리셋 시간 설정**
  - 기본 프리셋: 5분, 10분, 15분, 25분(포모도로), 30분, 45분, 1시간
  - 커스텀 프리셋 추가/편집/삭제
  - 드래그 앤 드롭으로 순서 변경

- ▶️ **타이머 컨트롤**
  - 시작/일시정지/재시작/리셋

- 🎨 **프리미엄 디자인**
  - 미니멀하고 깔끔한 UI
  - 다크/라이트 모드 자동 지원
  - 부드러운 애니메이션 효과
  - 그라디언트 색상 테마

## 시스템 요구사항

- macOS 13.0 (Ventura) 이상
- Xcode 14.0 이상

## 프로젝트 구조

```
TimeTimer/
├── TimeTimerApp.swift          # 앱 진입점
├── Info.plist                  # 앱 메타데이터
├── Models/
│   ├── TimerMode.swift         # 타이머 모드 enum
│   └── TimerPreset.swift       # 프리셋 데이터 모델
├── ViewModels/
│   └── TimerViewModel.swift    # 타이머 비즈니스 로직
├── Views/
│   ├── ContentView.swift       # 메인 화면
│   ├── BasicTimerView.swift    # 기본 타이머 뷰
│   ├── VisualTimerView.swift   # 원형 타이머 뷰
│   └── PresetManagementView.swift # 프리셋 관리 뷰
├── Utilities/
│   ├── NotificationManager.swift  # 알림 관리
│   └── ColorTheme.swift        # 색상 테마
└── Resources/
    └── Sounds/                 # 알림 사운드 (선택사항)
```

## 빌드 및 실행

### 1. Xcode에서 프로젝트 열기

```bash
cd /Users/hyeonseong/workspace/tools/TimeTimer
open TimeTimer.xcodeproj
```

### 2. 파일을 Xcode 프로젝트에 추가

> [!IMPORTANT]
> 파일들이 복사되었지만, Xcode 프로젝트에 아직 추가되지 않았을 수 있습니다.

Xcode에서:
1. 프로젝트 네비게이터에서 `TimeTimer` 폴더 우클릭
2. `Add Files to "TimeTimer"...` 선택
3. 다음 폴더들을 선택:
   - `Models`
   - `ViewModels`
   - `Views`
   - `Utilities`
   - `Resources`
4. 옵션 설정:
   - ✅ "Copy items if needed" 체크 해제 (이미 복사됨)
   - ✅ "Create groups" 선택
   - ✅ "TimeTimer" 타겟에 추가 체크
5. `Add` 클릭

또는 Finder에서 해당 폴더들을 Xcode 프로젝트 네비게이터로 드래그 앤 드롭하세요.

### 3. 빌드 설정 확인

1. 프로젝트 파일 선택 > `TARGETS > TimeTimer`
2. `General` 탭:
   - **Minimum Deployments**: macOS 13.0
3. `Signing & Capabilities` 탭:
   - **Team**: 본인의 Team 선택

### 4. 빌드 및 실행

- `Cmd + B`: 빌드
- `Cmd + R`: 실행

## 사용 방법

1. **시간 설정**: 시/분/초 Picker로 원하는 시간 설정
2. **프리셋 사용**: 빠른 프리셋 버튼 클릭으로 즉시 시간 설정
3. **타이머 모드 선택**: 상단의 Segmented Control로 기본/시각적 모드 전환
4. **시작**: Start 버튼 클릭
5. **일시정지/재시작**: 타이머 실행 중 Pause/Resume 버튼 사용
6. **리셋**: Reset 버튼으로 타이머 초기화
7. **프리셋 관리**: 우측 상단 톱니바퀴 아이콘으로 프리셋 추가/편집/삭제

## 알림 권한

앱 최초 실행 시 알림 권한을 요청합니다. 타이머 완료 알림을 받으려면 권한을 허용해주세요.

시스템 설정에서 알림 권한을 변경할 수 있습니다:
`System Settings > Notifications > Time Timer`

## 문제 해결

### 빌드 에러: "No such module"

- 모든 파일이 올바른 타겟에 추가되었는지 확인
- 파일 인스펙터에서 "Target Membership" 확인

### 파일이 Xcode에 보이지 않음

- Xcode 프로젝트를 닫고 다시 열기
- 또는 위의 "파일을 Xcode 프로젝트에 추가" 단계 수행

## 라이선스

MIT License

## 개발자

Created with ❤️ using SwiftUI
