# Google Drive API 설정 가이드

`downloader.py`에서 Google Drive 폴더를 다운로드하려면 Google Cloud Console에서 OAuth 2.0 인증 정보를 설정해야 합니다.

## 1단계: Google Cloud 프로젝트 생성

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택

## 2단계: Google Drive API 활성화

1. 좌측 메뉴에서 **"API 및 서비스"** > **"라이브러리"** 선택
2. "Google Drive API" 검색
3. **"사용 설정"** 클릭

## 3단계: OAuth 동의 화면 설정

1. 좌측 메뉴에서 **"API 및 서비스"** > **"OAuth 동의 화면"** 선택
2. 사용자 유형: **"외부"** 선택 (개인 사용자)
3. 앱 정보 입력:
   - 앱 이름: `Downloader` (원하는 이름)
   - 사용자 지원 이메일: 본인 이메일
   - 개발자 연락처 정보: 본인 이메일
4. **"저장 후 계속"** 클릭
5. 범위 추가는 건너뛰기
6. 테스트 사용자 추가 (본인 Gmail 주소 추가)
7. 완료

## 4단계: OAuth 2.0 클라이언트 ID 생성

1. 좌측 메뉴에서 **"API 및 서비스"** > **"사용자 인증 정보"** 선택
2. 상단의 **"+ 사용자 인증 정보 만들기"** > **"OAuth 클라이언트 ID"** 클릭
3. 애플리케이션 유형: **"데스크톱 앱"** 선택
4. 이름: `Downloader Desktop` (원하는 이름)
5. **"만들기"** 클릭

## 5단계: credentials.json 다운로드

1. 생성된 OAuth 클라이언트 ID 옆의 **다운로드 아이콘** 클릭
2. 다운로드한 JSON 파일 이름을 `credentials.json`으로 변경
3. `credentials.json` 파일을 `downloader.py`와 같은 디렉토리에 저장

## 6단계: 다운로더 실행

```bash
cd /Users/hyeonseong/workspace/tools
python downloader.py
```

메뉴에서 **"3. Google Drive 폴더 다운로드"** 선택 후 URL 입력

## 최초 실행 시

- 브라우저가 자동으로 열립니다
- Google 계정으로 로그인
- 앱 권한 승인 (경고 화면이 나오면 "고급" > "이동" 클릭)
- 인증 완료 후 `token.pickle` 파일이 자동 생성됩니다
- 이후에는 자동으로 인증됩니다

## 문제 해결

### "credentials.json 파일을 찾을 수 없습니다" 오류
- `credentials.json` 파일이 `downloader.py`와 같은 디렉토리에 있는지 확인

### "폴더 정보 조회 실패" 오류
- Google Drive 폴더 공유 설정이 "링크가 있는 모든 사용자"로 되어 있는지 확인
- 또는 인증한 Google 계정으로 해당 폴더에 접근 권한이 있는지 확인

### 권한 오류
- OAuth 동의 화면에서 테스트 사용자로 본인 이메일이 추가되어 있는지 확인
