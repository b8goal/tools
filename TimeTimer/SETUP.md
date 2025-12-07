# Xcode 프로젝트 파일 추가 가이드

모든 Swift 소스 파일이 `/Users/hyeonseong/workspace/tools/TimeTimer/TimeTimer/` 폴더에 복사되었습니다.

이제 Xcode에서 이 파일들을 프로젝트에 추가해야 합니다.

## 빠른 시작

### 1. Xcode 프로젝트가 이미 열려있는 경우

Xcode가 자동으로 새 파일들을 감지했을 수 있습니다. 프로젝트 네비게이터를 확인하세요.

### 2. 파일이 보이지 않는 경우

#### 방법 A: Finder에서 드래그 앤 드롭 (가장 쉬움)

1. Finder를 엽니다
2. `/Users/hyeonseong/workspace/tools/TimeTimer/TimeTimer/` 폴더로 이동
3. 다음 폴더들을 선택:
   - `Models`
   - `ViewModels`
   - `Views`
   - `Utilities`
   - `Resources`
4. 선택한 폴더들을 Xcode의 프로젝트 네비게이터에서 `TimeTimer` 폴더 위로 드래그
5. 나타나는 다이얼로그에서:
   - ❌ "Copy items if needed" 체크 해제 (이미 올바른 위치에 있음)
   - ✅ "Create groups" 선택
   - ✅ "Add to targets: TimeTimer" 체크
   - `Finish` 클릭

#### 방법 B: Xcode 메뉴 사용

1. Xcode에서 프로젝트 네비게이터의 `TimeTimer` 폴더 우클릭
2. `Add Files to "TimeTimer"...` 선택
3. 위의 폴더들을 선택하고 `Add` 클릭

### 3. 빌드 테스트

1. `Cmd + B`로 빌드
2. 에러가 없으면 성공!
3. `Cmd + R`로 앱 실행

## 예상되는 프로젝트 구조

빌드 성공 후 Xcode 프로젝트 네비게이터는 다음과 같아야 합니다:

```
TimeTimer
├── TimeTimerApp.swift
├── Models
│   ├── TimerMode.swift
│   └── TimerPreset.swift
├── ViewModels
│   └── TimerViewModel.swift
├── Views
│   ├── ContentView.swift
│   ├── BasicTimerView.swift
│   ├── VisualTimerView.swift
│   └── PresetManagementView.swift
├── Utilities
│   ├── NotificationManager.swift
│   └── ColorTheme.swift
├── Resources
│   └── Sounds
├── Assets.xcassets
└── Info.plist
```

## 문제 해결

### "No such module" 에러

파일이 타겟에 추가되지 않았습니다:
1. 파일 선택
2. 우측 인스펙터에서 "Target Membership" 확인
3. "TimeTimer" 체크박스 선택

### 파일이 회색으로 표시됨

파일 경로가 잘못되었습니다:
1. 파일 삭제 (참조만 삭제)
2. 위의 방법으로 다시 추가

### 빌드는 되는데 파일이 안 보임

Xcode 재시작:
1. `Cmd + Q`로 Xcode 종료
2. Xcode 다시 실행
3. 프로젝트 다시 열기

## 완료!

모든 파일이 추가되면 `Cmd + R`로 앱을 실행하세요! 🎉
