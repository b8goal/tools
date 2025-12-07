# 통합 다운로더 (Unified Downloader)

Korea University LMS와 Zoom 녹화 영상을 다운로드하는 통합 다운로더입니다.

## 기능

- **Korea University LMS 영상 다운로드**: API 기반 다운로드
- **Zoom 공유 링크 다운로드**: yt-dlp 기반 다운로드
- **배치 처리**: 여러 영상을 한 번에 다운로드
- **진행 상황 표시**: tqdm을 이용한 실시간 진행 상황 표시
- **자동 제목 추출**: API를 통한 영상 제목 자동 조회

## 설치

### 필수 요구사항

- Python 3.7 이상
- pip

### 라이브러리 설치

```bash
pip install requests tqdm yt-dlp
```

## 사용법

### Python 스크립트로 실행

```python
python downloader.py
```

## 주요 함수

### LMS 영상 다운로드

- `extract_content_id_from_url(url)`: LMS 페이지 URL에서 content_id 추출
- `get_video_title_from_api(content_id)`: API를 통해 영상 제목 조회
- `download_video_requests(url, filename, output_path, index)`: requests를 이용한 영상 다운로드

### Zoom 영상 다운로드

- yt-dlp를 이용한 공유 링크 다운로드 지원

## 출력 디렉토리

다운로드된 영상은 기본적으로 `./m3u8DL` 디렉토리에 저장됩니다.

## 라이선스

MIT

## 주의사항

- 다운로드한 콘텐츠는 개인 학습용으로만 사용하세요
- 저작권 법률을 준수하세요
