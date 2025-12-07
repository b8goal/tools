#!/usr/bin/env python3
"""
통합 다운로더 - Korea University LMS + Zoom 녹화 + Google Drive
- Korea University LMS 영상 (API 기반)
- Zoom 공유 링크 (yt-dlp 기반)
- Google Drive 폴더 (Google Drive API 기반)
- 배치 처리 지원
"""
import requests
import xml.etree.ElementTree as ET
import re
import os
import subprocess
from tqdm import tqdm
from urllib.parse import urlparse
import time
import pickle
import io
from pathlib import Path

# Google Drive API imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False

# Google Drive API 권한 범위
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def extract_content_id_from_url(url):
    """URL에서 content_id 추출 (LMS 페이지 URL)"""
    match = re.search(r'/em/([a-f0-9]+)$', url)
    if match:
        return match.group(1)
    return None

def extract_content_id_from_mp4(url):
    """직접 MP4 URL에서 content_id 추출"""
    match = re.search(r'/kruniv1001/([a-f0-9]+)/', url)
    if match:
        return match.group(1)
    return None

def get_video_title_from_api(content_id):
    """API에서 비디오 제목 조회"""
    try:
        api_url = f"https://kucom.korea.ac.kr/viewer/ssplayer/uniplayer_support/content.php?content_id={content_id}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.text)
        title_elem = root.find('.//title')
        if title_elem is not None:
            return title_elem.text
        return None
    except Exception:
        return None

def download_video_requests(url, filename, output_path="./downloads", index=None):
    """requests 라이브러리를 사용한 비디오 다운로드"""
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    # 파일명에서 특수문자 제거
    filename = re.sub(r'[\\/:*?"<>|]', '', filename)
    if not filename.endswith(('.mp4', '.mov', '.mkv')):
        filename += '.mp4'
    
    file_path = os.path.join(output_path, filename)
    
    # 중복 파일명 처리
    if os.path.exists(file_path):
        name, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(os.path.join(output_path, f"{name}_{counter}{ext}")):
            counter += 1
        file_path = os.path.join(output_path, f"{name}_{counter}{ext}")
    
    prefix = f"[{index}] " if index else ""
    print(f"\n{prefix}📥 다운로드 시작: {filename}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'Referer': 'https://kucom.korea.ac.kr/',
        }
        
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(file_path, 'wb') as f, tqdm(
            desc=os.path.basename(file_path),
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as progress_bar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    progress_bar.update(len(chunk))
        
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size > 0:
                size_mb = file_size / (1024**2)
                print(f"{prefix}✅ 완료! ({size_mb:.2f} MB)")
                return True, file_path
            else:
                print(f"{prefix}⚠️ 파일이 비어있습니다")
                os.remove(file_path)
                return False, None
        else:
            print(f"{prefix}❌ 파일 생성 실패")
            return False, None
            
    except Exception as e:
        print(f"{prefix}❌ 다운로드 오류: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        return False, None

def download_video_ytdlp(url, filename, output_path="./downloads", index=None):
    """yt-dlp를 사용한 비디오 다운로드 (Zoom 등)"""
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    prefix = f"[{index}] " if index else ""
    print(f"\n{prefix}📥 yt-dlp로 다운로드 시작: {filename}")
    
    try:
        # yt-dlp 명령어 실행
        cmd = [
            'yt-dlp',
            '-f', 'best',
            '-o', os.path.join(output_path, f"{filename}.%(ext)s"),
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # 다운로드된 파일 찾기
            for file in os.listdir(output_path):
                if filename in file and file.endswith(('.mp4', '.mkv', '.mov')):
                    file_path = os.path.join(output_path, file)
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        if file_size > 0:
                            size_mb = file_size / (1024**2)
                            print(f"{prefix}✅ 완료! ({size_mb:.2f} MB)")
                            return True, file_path
            
            print(f"{prefix}⚠️ 다운로드 파일을 찾을 수 없습니다")
            return False, None
        else:
            print(f"{prefix}❌ yt-dlp 오류:")
            print(f"   {result.stderr[:200]}")
            return False, None
            
    except subprocess.TimeoutExpired:
        print(f"{prefix}❌ 다운로드 시간 초과")
        return False, None
    except FileNotFoundError:
        print(f"{prefix}❌ yt-dlp을 찾을 수 없습니다. 설치해주세요: pip install yt-dlp")
        return False, None
    except Exception as e:
        print(f"{prefix}❌ 오류: {e}")
        return False, None

def get_gdrive_service():
    """Google Drive API 서비스 인증 및 반환"""
    if not GDRIVE_AVAILABLE:
        print("❌ Google Drive API 라이브러리가 설치되지 않았습니다.")
        print("   다음 명령어로 설치하세요: pip install google-auth google-auth-oauthlib google-api-python-client")
        return None
    
    creds = None
    token_file = 'token.pickle'
    credentials_file = 'credentials.json'
    
    # 저장된 토큰 로드
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
    
    # 토큰이 없거나 만료된 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 토큰 갱신 중...")
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_file):
                print("\n❌ credentials.json 파일을 찾을 수 없습니다.")
                print("\n📋 Google Drive API 설정 방법:")
                print("1. https://console.cloud.google.com/ 접속")
                print("2. 프로젝트 생성 또는 선택")
                print("3. 'API 및 서비스' > 'OAuth 동의 화면' 설정")
                print("4. 'API 및 서비스' > '사용자 인증 정보' > 'OAuth 2.0 클라이언트 ID' 생성")
                print("5. 애플리케이션 유형: '데스크톱 앱' 선택")
                print("6. 생성된 credentials.json 파일을 현재 디렉토리에 저장")
                print("\n자세한 가이드: https://developers.google.com/drive/api/quickstart/python\n")
                return None
            
            print("🔐 Google 계정 인증 중... (브라우저가 열립니다)")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 토큰 저장
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)
        print("✅ 인증 완료!")
    
    return build('drive', 'v3', credentials=creds)

def extract_gdrive_folder_id(url):
    """Google Drive URL에서 폴더 ID 추출"""
    patterns = [
        r'folders/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def list_gdrive_folder_contents(service, folder_id, path=""):
    """
    Google Drive 폴더의 모든 파일과 하위 폴더를 재귀적으로 탐색
    Returns: [(file_id, file_name, file_path, mime_type), ...]
    """
    items = []
    page_token = None
    
    try:
        while True:
            query = f"'{folder_id}' in parents and trashed=false"
            results = service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token
            ).execute()
            
            files = results.get('files', [])
            
            for file in files:
                file_id = file['id']
                file_name = file['name']
                mime_type = file['mimeType']
                file_path = os.path.join(path, file_name)
                
                if mime_type == 'application/vnd.google-apps.folder':
                    # 하위 폴더 재귀 탐색
                    items.extend(list_gdrive_folder_contents(service, file_id, file_path))
                else:
                    # 파일 추가
                    items.append((file_id, file_name, file_path, mime_type))
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
    
    except Exception as e:
        print(f"❌ 폴더 탐색 오류: {e}")
    
    return items

def download_gdrive_file(service, file_id, file_name, file_path, output_path, index=None):
    """Google Drive 파일 다운로드"""
    prefix = f"[{index}] " if index else ""
    
    # 전체 경로 생성
    full_path = os.path.join(output_path, file_path)
    dir_path = os.path.dirname(full_path)
    
    # 디렉토리 생성
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    # 중복 파일명 처리
    if os.path.exists(full_path):
        name, ext = os.path.splitext(full_path)
        counter = 1
        while os.path.exists(f"{name}_{counter}{ext}"):
            counter += 1
        full_path = f"{name}_{counter}{ext}"
    
    print(f"\n{prefix}📥 다운로드: {file_path}")
    
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(full_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        with tqdm(total=100, desc=os.path.basename(file_path), unit='%') as pbar:
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    pbar.update(progress - pbar.n)
        
        fh.close()
        
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path)
            if file_size > 0:
                size_mb = file_size / (1024**2)
                print(f"{prefix}✅ 완료! ({size_mb:.2f} MB)")
                return True, full_path
            else:
                print(f"{prefix}⚠️ 파일이 비어있습니다")
                os.remove(full_path)
                return False, None
        else:
            print(f"{prefix}❌ 파일 생성 실패")
            return False, None
    
    except Exception as e:
        print(f"{prefix}❌ 다운로드 오류: {e}")
        if os.path.exists(full_path):
            os.remove(full_path)
        return False, None

def download_gdrive_folder(url, output_path="./downloads"):
    """Google Drive 폴더 전체 다운로드"""
    print("\n" + "=" * 70)
    print("📁 Google Drive 폴더 다운로드")
    print("=" * 70)
    
    # 폴더 ID 추출
    folder_id = extract_gdrive_folder_id(url)
    if not folder_id:
        print("❌ 유효하지 않은 Google Drive 폴더 URL입니다.")
        return 0, 1
    
    print(f"📌 폴더 ID: {folder_id}")
    
    # Google Drive API 서비스 인증
    service = get_gdrive_service()
    if not service:
        return 0, 1
    
    # 폴더 정보 조회
    try:
        folder_info = service.files().get(fileId=folder_id, fields='name').execute()
        folder_name = folder_info.get('name', 'Unknown')
        print(f"📝 폴더 이름: {folder_name}")
    except Exception as e:
        print(f"❌ 폴더 정보 조회 실패: {e}")
        print("\n💡 권한 확인:")
        print("   - 폴더 공유 설정이 '링크가 있는 모든 사용자'로 되어 있는지 확인")
        print("   - Google 계정으로 해당 폴더에 접근 권한이 있는지 확인\n")
        return 0, 1
    
    # 폴더 내용 탐색
    print("\n🔍 폴더 내용 탐색 중...")
    files = list_gdrive_folder_contents(service, folder_id)
    
    if not files:
        print("⚠️ 폴더에 다운로드할 파일이 없습니다.")
        return 0, 0
    
    print(f"\n📊 총 {len(files)}개의 파일 발견\n")
    
    # 파일 다운로드
    successful = 0
    failed = 0
    
    for i, (file_id, file_name, file_path, mime_type) in enumerate(files, 1):
        # Google Docs 형식 파일은 건너뛰기
        if mime_type.startswith('application/vnd.google-apps.'):
            print(f"\n[{i}] ⏭️ 건너뛰기 (Google Docs 형식): {file_path}")
            continue
        
        success, filepath = download_gdrive_file(service, file_id, file_name, file_path, output_path, i)
        
        if success:
            successful += 1
        else:
            failed += 1
        
        if i < len(files):
            time.sleep(0.3)
    
    # 최종 결과
    print(f"\n\n{'=' * 70}")
    print("📊 다운로드 결과")
    print("=" * 70)
    print(f"✅ 성공: {successful}")
    print(f"❌ 실패: {failed}")
    print(f"📁 저장위치: {output_path}/")
    print("=" * 70)
    
    return successful, failed

def process_url(url, index, output_path="./downloads"):
    """
    URL 타입 자동 감지 및 처리
    - Korea University LMS URL
    - Zoom 공유 링크
    - 직접 MP4 URL
    """
    url = url.strip()
    
    if not url:
        return False, None
    
    print(f"\n{'=' * 70}")
    print(f"[{index}] 처리 중...")
    print(f"URL: {url[:100]}...")
    
    # Zoom URL인 경우 - yt-dlp 사용
    if 'zoom.us' in url:
        print("🎯 감지: Zoom 녹화 링크")
        filename = f"Zoom_Recording_{index}"
        return download_video_ytdlp(url, filename, output_path, index)
    
    # Korea University 직접 MP4 URL
    if 'korea-cms-object.cdn.gov-ntruss.com' in url:
        print("🎯 감지: Korea University CDN URL")
        content_id = extract_content_id_from_mp4(url)
        if content_id:
            title = get_video_title_from_api(content_id)
            if not title:
                title = f"Lecture_{index}"
            print(f"📌 content_id: {content_id}")
            print(f"📝 제목: {title}")
            return download_video_requests(url, title, output_path, index)
    
    # Korea University LMS 페이지 URL
    elif 'kucom.korea.ac.kr/em/' in url:
        print("🎯 감지: Korea University LMS 페이지")
        content_id = extract_content_id_from_url(url)
        if content_id:
            print(f"📌 content_id: {content_id}")
            
            title = get_video_title_from_api(content_id)
            if not title:
                title = f"Lecture_{index}"
            
            print(f"📝 제목: {title}")
            
            download_url = f"https://korea-cms-object.cdn.gov-ntruss.com/contents7/kruniv1001/{content_id}/contents/media_files/screen.mp4"
            return download_video_requests(download_url, title, output_path, index)
    
    # Google Drive URL인 경우
    if 'drive.google.com' in url and 'folders' in url:
        print("🎯 감지: Google Drive 폴더")
        # Google Drive는 별도 함수로 처리
        return False, "GDRIVE_FOLDER"
    
    print("❌ 인식할 수 없는 URL 형식")
    return False, None

def interactive_mode(output_path="./downloads"):
    """대화형 모드 - 사용자 입력"""
    print("\n" + "=" * 70)
    print("📝 대화형 모드")
    print("=" * 70)
    print("\n다운로드할 URL을 입력하세요 (한 줄에 하나씩, 빈 줄 입력하면 시작):\n")
    
    urls = []
    while True:
        url = input(f"URL {len(urls)+1}: ").strip()
        if not url:
            if urls:
                break
            else:
                print("최소 하나의 URL을 입력해주세요")
                continue
        urls.append(url)
    
    return batch_download(urls, output_path)

def batch_download(urls, output_path="./downloads"):
    """배치 다운로드"""
    print("\n" + "=" * 70)
    print("🎓 통합 다운로더 - 배치 모드")
    print("=" * 70)
    print(f"\n📊 총 {len(urls)}개의 영상 다운로드\n")
    
    results = []
    successful = 0
    failed = 0
    
    for i, url in enumerate(urls, 1):
        success, filepath = process_url(url, i, output_path)
        results.append((i, url[:50], success, filepath))
        
        if success:
            successful += 1
        else:
            failed += 1
        
        if i < len(urls):
            time.sleep(0.5)
    
    # 최종 결과
    print(f"\n\n{'=' * 70}")
    print("📊 다운로드 결과")
    print("=" * 70)
    print(f"✅ 성공: {successful}")
    print(f"❌ 실패: {failed}")
    print(f"📁 저장위치: {output_path}/")
    print("=" * 70)
    
    return successful, failed

def main():
    """메인 함수"""
    print("\n" + "=" * 70)
    print("🎓 Korea University LMS + Zoom + Google Drive 통합 다운로더")
    print("=" * 70)
    print("\n선택해주세요:")
    print("1. 대화형 모드 (URL 직접 입력)")
    print("2. 배치 다운로드 (코드에 URL 입력)")
    print("3. Google Drive 폴더 다운로드")
    print()
    
    choice = input("선택 (1, 2, 또는 3): ").strip()
    
    if choice == "1":
        interactive_mode()
    elif choice == "3":
        print("\n📁 Google Drive 폴더 URL을 입력하세요:")
        gdrive_url = input("URL: ").strip()
        if gdrive_url:
            download_gdrive_folder(gdrive_url)
        else:
            print("❌ URL이 입력되지 않았습니다.")
    else:
        # 배치 모드 - 여기에 URL 추가
        urls = [
            # Korea University 예제
            # "https://kucom.korea.ac.kr/em/68b990277e5c3",
            # "https://korea-cms-object.cdn.gov-ntruss.com/contents7/kruniv1001/68b990277e5c3/contents/media_files/screen.mp4",
            
            # Zoom 예제
            # "https://korea-ac-kr.zoom.us/rec/play/...",
            
            # Google Drive 예제
            # "https://drive.google.com/drive/folders/11veeKAuMrJTYWaj5SshLVoe81zh5Wckp",
        ]
        
        if not urls:
            print("\n❌ 배치 모드에 URL이 없습니다.")
            print("   코드를 수정하거나 대화형 모드를 사용해주세요.")
            return
        
        batch_download(urls)

if __name__ == "__main__":
    main()
