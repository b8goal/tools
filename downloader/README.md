# Downloader - 통합 다운로더

Korea University LMS, Zoom 녹화, Google Drive 폴더를 다운로드할 수 있는 통합 다운로더입니다.

## 기능

- ✅ **Korea University LMS 영상** - API 기반 다운로드
- ✅ **Zoom 공유 링크** - yt-dlp 기반 다운로드
- ✅ **Google Drive 폴더** - Google Drive API 기반 재귀적 다운로드
- ✅ **배치 처리** - 여러 URL 한번에 다운로드

## 설치

### 1. 필수 라이브러리 설치

```bash
pip install requests tqdm yt-dlp google-auth google-auth-oauthlib google-api-python-client
```

### 2. Google Drive API 설정 (선택사항)

Google Drive 폴더를 다운로드하려면 OAuth 인증이 필요합니다.

자세한 설정 방법은 [docs/GDRIVE_SETUP.md](docs/GDRIVE_SETUP.md)를 참고하세요.

## 사용 방법

### 기본 실행

```bash
cd /Users/hyeonseong/workspace/tools/downloader
python downloader.py
```

### 메뉴 선택

```
🎓 Korea University LMS + Zoom + Google Drive 통합 다운로더

선택해주세요:
1. 대화형 모드 (URL 직접 입력)
2. 배치 다운로드 (코드에 URL 입력)
3. Google Drive 폴더 다운로드
```

### 1. 대화형 모드

URL을 하나씩 입력하여 다운로드합니다.

```
선택 (1, 2, 또는 3): 1

URL 1: https://kucom.korea.ac.kr/em/68b990277e5c3
URL 2: https://korea-ac-kr.zoom.us/rec/play/...
URL 3: (빈 줄 입력하면 시작)
```

### 2. 배치 다운로드

`downloader.py` 파일을 열어 `urls` 리스트에 URL을 추가합니다:

```python
urls = [
    "https://kucom.korea.ac.kr/em/68b990277e5c3",
    "https://korea-ac-kr.zoom.us/rec/play/...",
]
```

### 3. Google Drive 폴더 다운로드

```
선택 (1, 2, 또는 3): 3

📁 Google Drive 폴더 URL을 입력하세요:
URL: https://drive.google.com/drive/folders/11veeKAuMrJTYWaj5SshLVoe81zh5Wckp
```

## 지원 URL 형식

### Korea University LMS
- 페이지 URL: `https://kucom.korea.ac.kr/em/[content_id]`
- 직접 MP4 URL: `https://korea-cms-object.cdn.gov-ntruss.com/contents7/kruniv1001/[content_id]/contents/media_files/screen.mp4`

### Zoom
- 공유 링크: `https://korea-ac-kr.zoom.us/rec/play/...`

### Google Drive
- 폴더 URL: `https://drive.google.com/drive/folders/[folder_id]`
- 공유 링크: `https://drive.google.com/drive/folders/[folder_id]?usp=share_link`

## 다운로드 위치

기본 다운로드 위치: `./downloads/`

Google Drive 폴더는 폴더 구조를 유지하며 다운로드됩니다.

## 문제 해결

### Google Drive 인증 오류

**"credentials.json 파일을 찾을 수 없습니다"**
- [docs/GDRIVE_SETUP.md](docs/GDRIVE_SETUP.md) 가이드를 따라 설정

**"액세스 차단됨: 403 오류"**
- OAuth 동의 화면에서 테스트 사용자로 본인 Gmail 추가

### yt-dlp 오류

**"yt-dlp을 찾을 수 없습니다"**
```bash
pip install yt-dlp
```

## 프로젝트 구조

```
downloader/
├── downloader.py          # 메인 스크립트
├── credentials.json       # Google OAuth 인증 정보 (사용자가 생성)
├── token.pickle          # Google 인증 토큰 캐시 (자동 생성)
├── docs/
│   └── GDRIVE_SETUP.md   # Google Drive API 설정 가이드
└── README.md             # 이 파일
```

## 라이선스

MIT License
