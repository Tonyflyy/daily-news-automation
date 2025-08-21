import os
import base64
import markdown
from email.mime.text import MIMEText
from urllib.parse import urljoin, urlparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.generativeai as genai
import feedparser
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import requests

def generate_ai_briefing(news_list):
    print("AI 서식화 브리핑 생성을 시작합니다...")
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("GEMINI_API_KEY가 설정되지 않았습니다.")
            return None
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        news_context = ""
        for news in news_list:
            news_context += f"제목: {news['title']}\n요약: {news['summary']}\n\n"
        prompt = f"""
        당신은 탁월한 통찰력을 가진 IT/경제 뉴스 큐레이터입니다.
        아래 뉴스 목록을 분석하여, 독자를 위한 매우 읽기 쉬운 '데일리 브리핑'을 작성해주세요.
        **출력 형식 규칙:**
        1. 전체 글은 두 부분으로 구성됩니다: '에디터 브리핑'과 '주요 뉴스 분석'.
        2. '에디터 브리핑'은 '## 에디터 브리핑' 헤더로 시작하며, 오늘 뉴스의 핵심을 2~3 문장으로 요약합니다.
        3. '주요 뉴스 분석'은 '## 주요 뉴스 분석' 헤더로 시작합니다.
        4. 주요 뉴스 분석에서는 가장 중요한 뉴스 카테고리 2~3개를 '###' 헤더로 구분해주세요 (예: '### 생성형 AI의 확산과 영향').
        5. 각 카테고리 안에서는 관련된 뉴스들을 글머리 기호(`*`)를 사용해 나열하고, 핵심 키워드는 **굵은 글씨**로 강조해주세요.
        6. 전체적으로 전문적인 톤을 유지하면서도, 문단 구분을 명확하게 하여 가독성을 극대화해주세요.
        [오늘의 뉴스 목록]
        {news_context}
        """
        response = model.generate_content(prompt)
        print("AI 서식화 브리핑 생성 성공!")
        return response.text
    except Exception as e:
        print(f"AI 브리핑 생성 중 오류 발생: {e}")
        return None

def get_image_from_url(page_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(page_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image['content']
            if image_url.startswith('/'):
                parsed_uri = urlparse(page_url)
                base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                image_url = urljoin(base_url, image_url)
            return image_url
    except Exception as e:
        print(f"이미지 URL 추출 중 오류 발생 (URL: {page_url}): {e}")
    return None

def update_sent_links(links):
    try:
        with open('sent_links.txt', 'a', encoding='utf-8') as f:
            for link in links:
                f.write(link + '\n')
        print(f"{len(links)}개의 새 링크를 sent_links.txt에 추가했습니다.")
    except Exception as e:
        print(f"sent_links.txt 파일 업데이트 중 오류 발생: {e}")

def get_news_from_rss():
    sent_links = set()
    try:
        with open('sent_links.txt', 'r', encoding='utf-8') as f:
            sent_links = set(line.strip() for line in f)
        print(f"총 {len(sent_links)}개의 보낸 기록을 sent_links.txt에서 불러왔습니다.")
    except FileNotFoundError:
        print("sent_links.txt 파일을 찾을 수 없어, 새로운 기록을 시작합니다.")
    
    rss_feeds = [
        'https://www.zdnet.co.kr/rss/all.xml', 'https://www.etnews.com/rss/all.xml',
        'https://www.itworld.co.kr/rss', 'https://www.ciokorea.com/rss',
        'https://www.bloter.net/rss', 'http://www.ddaily.co.kr/rss.xml',
        'https://www.hankyung.com/feed/it', 'https://www.mk.co.kr/rss/all.xml',
        'https://rss.mt.co.kr/mt_all.xml', 'https://news.einfomax.co.kr/rss/clickTop.xml',
        'https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml',
        'https://rss.joins.com/joins_news_list.xml', 'https://rss.donga.com/total.xml',
        'https://www.hani.co.kr/rss'
    ]
    
    found_news = []
    unique_links = set()
    print("RSS 피드를 통해 뉴스 수집을 시작합니다...")
    for url in rss_feeds:
        try:
            feed = feedparser.parse(url, agent='Mozilla/5.0')
            for entry in feed.entries:
                if entry.link in sent_links or entry.link in unique_links:
                    continue
                
                summary_html = entry.get('summary', '요약 없음')
                soup = BeautifulSoup(summary_html, 'lxml')
                summary_text = soup.get_text(strip=True)
                
                keywords = [
                    'AI', '인공지능', '머신러닝', '딥러닝', 'LLM', '생성형', 'ChatGPT', 'Gemini', 
                    'AI반도체', 'HBM', 'CXL', '주식', '증시', '코스피', '나스닥', '금리', 
                    '환율', '실적', '투자', 'M&A', '삼성전자', 'SK하이닉스', '엔비디아', 
                    '네이버', '카카오', '구글', '애플', 'MS', '클라우드', '데이터', '빅데이터'
                ]
                search_text = entry.title + " " + summary_text
                
                for keyword in keywords:
                    if keyword.lower() in search_text.lower():
                        image_url = get_image_from_url(entry.link)
                        news_item = {
                            'title': entry.title,
                            'link': entry.link,
                            'summary': summary_text[:150] + '...',
                            'image_url': image_url
                        }
                        found_news.append(news_item)
                        unique_links.add(entry.link)
                        break
        except Exception as e:
            print(f"'{url}' 처리 중 오류 발생: {e}")

    print(f"총 {len(found_news)}개의 새로운 뉴스를 찾았습니다.")
    return found_news

def create_email_html(news_list, ai_briefing):
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('email_template.html')
    today_date = datetime.now().strftime("%Y-%m-%d")
    return template.render(news_list=news_list, today_date=today_date, ai_briefing=ai_briefing)

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

if __name__ == "__main__":
    RECEIVER_EMAIL = "rjh@ylp.co.kr"
    news_data = get_news_from_rss()
    if news_data:
        ai_briefing_markdown = generate_ai_briefing(news_data)
        ai_briefing_html = markdown.markdown(ai_briefing_markdown) if ai_briefing_markdown else None
        email_body = create_email_html(news_data, ai_briefing_html)
        email_subject = f"[{datetime.now().strftime('%Y-%m-%d')}] 오늘의 AI/주식/머신러닝 뉴스"
        send_email_oauth(RECEIVER_EMAIL, email_subject, email_body)
        new_links_to_save = [news['link'] for news in news_data]
        update_sent_links(new_links_to_save)
    else:
        print("발송할 새로운 뉴스가 없습니다.")
