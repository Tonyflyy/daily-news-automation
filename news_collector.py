# news_collector.py (이미지 썸네일 기능 추가 버전)

import os.path
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import feedparser
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import requests # 웹 페이지 요청을 위해 추가

# --- 새로 추가된 기능: URL에서 대표 이미지(og:image) 가져오기 ---
def get_image_from_url(url):
    """
    주어진 URL의 웹 페이지에서 Open Graph(og:image) 이미지 주소를 추출합니다.
    """
    try:
        # 일부 웹사이트는 봇의 접근을 막기 때문에, 일반 브라우저처럼 보이도록 헤더를 추가합니다.
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # 오류가 발생하면 예외를 발생시킴

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 'og:image' 메타 태그를 찾아 이미지 URL을 반환합니다.
        og_image = soup.find('meta', property='og:image')
        
        if og_image and og_image.get('content'):
            return og_image['content']
            
    except Exception as e:
        print(f"이미지 URL 추출 중 오류 발생 (URL: {url}): {e}")
        
    # 이미지를 찾지 못했거나 오류가 발생하면 None을 반환합니다.
    return None

# --- 1. 뉴스 수집 기능 (이미지 URL 가져오는 부분 추가) ---
def get_news_from_rss():
    keywords = [
        '생성형 AI', 'LLM', 'Gemini', 'ChatGPT', '인공지지능 윤리', 'AI 반도체',
        '증시', '코스피', '나스닥', '반도체', '테마주', '금리', '실적 발표',
        '딥러닝', '강화학습', '데이터 과학', '컴퓨터 비전', '자연어 처리', 'NLP'
    ]
    rss_feeds = [
        'https://www.zdnet.co.kr/rss/all.xml',
        'https://www.etnews.com/rss/all.xml',
        'https://www.itworld.co.kr/rss',
        'https://news.einfomax.co.kr/rss/clickTop.xml',
        'https://www.hankyung.com/feed/it'
    ]
    found_news = []
    unique_links = set()
    print("뉴스 수집을 시작합니다...")
    for url in rss_feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if entry.link in unique_links:
                    continue
                search_text = entry.title + " " + entry.get('summary', '')
                for keyword in keywords:
                    if keyword.lower() in search_text.lower():
                        summary_html = entry.get('summary', '요약 없음')
                        soup = BeautifulSoup(summary_html, 'lxml')
                        summary_text = soup.get_text(strip=True)
                        
                        # --- 이 부분이 수정되었습니다 ---
                        # 각 기사 링크에서 대표 이미지 URL을 가져옵니다.
                        image_url = get_image_from_url(entry.link)
                        
                        news_item = {
                            'title': entry.title,
                            'link': entry.link,
                            'summary': summary_text[:150] + '...',
                            'image_url': image_url  # 딕셔너리에 이미지 URL 추가
                        }
                        # --- 여기까지 ---
                        
                        found_news.append(news_item)
                        unique_links.add(entry.link)
                        break
        except Exception as e:
            print(f"'{url}' 처리 중 오류 발생: {e}")
    print(f"총 {len(found_news)}개의 뉴스를 찾았습니다.")
    return found_news

# --- 2. 이메일 HTML 생성 기능 (변경 없음) ---
def create_email_html(news_list):
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('email_template.html')
    today_date = datetime.now().strftime("%Y-%m-%d")
    return template.render(news_list=news_list, today_date=today_date)

# --- 3. OAuth 인증 및 이메일 발송 기능 (변경 없음) ---
def send_email_oauth(receiver_email, subject, body):
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    try:
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEText(body, 'html')
        message['To'] = receiver_email
        message['Subject'] = subject
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}
        send_message = (service.users().messages().send(userId="me", body=create_message).execute())
        print(F'메시지 ID: {send_message["id"]} 이메일 발송 성공!')
    except HttpError as error:
        print(F'이메일 발송 중 오류 발생: {error}')

# --- 메인 코드 실행 부분 (변경 없음) ---
if __name__ == "__main__":
    RECEIVER_EMAIL = "rjh@ylp.co.kr"
    news_data = get_news_from_rss()
    if news_data:
        email_body = create_email_html(news_data)
        email_subject = f"[{datetime.now().strftime('%Y-%m-%d')}] 오늘의 AI/주식/머신러닝 뉴스"
        send_email_oauth(RECEIVER_EMAIL, email_subject, email_body)
    else:
        print("발송할 뉴스가 없습니다.")