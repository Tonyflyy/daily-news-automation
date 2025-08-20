# news_collector.py (OAuth 2.0 최종 버전)

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

# --- 1. 뉴스 수집 기능 (변경 없음) ---
def get_news_from_rss():
    keywords = [
        '생성형 AI', 'LLM', 'Gemini', 'ChatGPT', '인공지능 윤리', 'AI 반도체',
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
                        news_item = {
                            'title': entry.title,
                            'link': entry.link,
                            'summary': summary_text[:150] + '...'
                        }
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

# --- 3. OAuth 인증 및 이메일 발송 기능 (완전히 새로 작성) ---
def send_email_oauth(receiver_email, subject, body):
    # Gmail API가 이메일 발송을 할 수 있도록 허용 범위를 지정합니다.
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    creds = None
    
    # 'token.json' 파일이 있는지 확인합니다. 이 파일은 사용자의 인증 정보를 저장합니다.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 'token.json'이 없거나, 유효하지 않은 경우 사용자가 직접 로그인하여 새로 만듭니다.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 'credentials.json' 파일을 이용해 인증 절차를 시작합니다.
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 생성된 인증 정보를 다음 실행을 위해 'token.json' 파일로 저장합니다.
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # Gmail API 서비스를 생성합니다.
        service = build('gmail', 'v1', credentials=creds)
        
        # 이메일 메시지를 생성합니다.
        message = MIMEText(body, 'html')
        message['To'] = receiver_email
        message['Subject'] = subject
        
        # Gmail API가 이해할 수 있는 base64 형식으로 인코딩합니다.
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}
        
        # Gmail API를 통해 이메일을 발송합니다. 'me'는 현재 인증된 사용자를 의미합니다.
        send_message = (service.users().messages().send(userId="me", body=create_message).execute())
        print(F'메시지 ID: {send_message["id"]} 이메일 발송 성공!')
    except HttpError as error:
        print(F'이메일 발송 중 오류 발생: {error}')

# --- 메인 코드 실행 부분 ---
if __name__ == "__main__":
    RECEIVER_EMAIL = "rjh@ylp.co.kr"
    
    # 1. 뉴스 수집
    news_data = get_news_from_rss()
    
    if news_data:
        # 2. 이메일 본문 생성
        email_body = create_email_html(news_data)
        
        # 3. 이메일 발송
        email_subject = f"[{datetime.now().strftime('%Y-%m-%d')}] 오늘의 AI/주식/머신러닝 뉴스"
        send_email_oauth(RECEIVER_EMAIL, email_subject, email_body)
    else:
        print("발송할 뉴스가 없습니다.")