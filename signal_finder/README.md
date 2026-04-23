# 📊 Signal Finder

주식 커뮤니티 사이트에서 투자 시그널을 자동 추출하여 Notion 데일리 페이지로 정리하는 시스템.

## 대상 사이트

| 사이트 | URL | 상태 |
|--------|-----|------|
| FM Korea 주식 | https://www.fmkorea.com/stock | ✅ v1 |
| 고파스 경제 | https://www.koreapas.com/bbs/zboard.php?id=econo | ✅ v1 |
| DC 미주갤 | https://gall.dcinside.com/mgallery/board/lists?id=stockus | ✅ v1 |
| 뽐뿌 증권포럼 | https://www.ppomppu.co.kr/zboard/zboard.php?id=stock | ✅ v1 |
| 클리앙 주식한당 | https://www.clien.net/service/board/cm_stock | ✅ v1 |
| 네이버 메르 블로그 | https://blog.naver.com/ranto28 | ✅ v1 |

## 설치

```bash
# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 편집하여 Notion API 토큰 등을 입력

# FM Korea 보안 페이지 대응용 (npx 필요)
node --version
npx --version
```

## Notion 설정

1. [Notion Integrations](https://www.notion.so/my-integrations)에서 Integration 생성
2. Internal Integration Secret을 `.env`의 `NOTION_TOKEN`에 입력
3. Notion에서 Signal Finder 결과를 저장할 페이지에 Integration 연결
4. 해당 페이지의 ID를 `.env`의 `NOTION_PARENT_PAGE_ID`에 입력

## 사용법

```bash
# 1회 실행 (테스트용)
python main.py --once

# 스케줄러 실행 (1시간 단위 자동 수집)
python main.py
```

## 수집 항목

각 글에 대해 다음 정보를 추출합니다:
- 🔗 원문 링크
- 📝 글 요약
- 💡 투자 인사이트
- 🏷️ 투자 키워드 (종목명, 티커)
- 💬 댓글 요약
- 📊 시그널 강도 (높음/중간/낮음)

## 라이선스

개인 사용 목적
