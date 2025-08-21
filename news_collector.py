# news_collector.py (이미지 썸네일 기능 추가 버전)

import os
import google.generativeai as genai
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


def generate_ai_briefing(news_titles):
    """
    뉴스 제목 목록을 잼민이 api에 보내 데일리 브리핑을 생성
    """
    print("AI 브리핑 생성을 시작합니다...")
    try:
        #환경 변수에서 API키를 가져옴
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("GEMINI_API_KEY가 설정되지 않았습니다.")
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        #AI에게 역할을 부여하고 지시하는 프롬프트
        prompt = f"""
        당신은 IT와 경제 뉴스를 분석하는 전문 뉴스 에디터입니다.
        아래는 오늘 수집된 주요 뉴스 제목 목록입니다.
        이 제목들을 바탕으로, 오늘 하루의 가장 중요한 기술 및 경제 트렌드를 요약하는 2~3 문장의 흥미로운 서두를 작성해주세요.
        독자들이 뉴스를 계속 읽고 싶게 만들어야 합니다. 격식 있고 전문적인 톤을 유지해주세요.

        [뉴스 제목 목록]
        - {'\n- '.join(news_titles)}
        """

        response = model.generate_content(prompt)
        print("AI 브리핑 생성 성공!")
        return response.text
    except Exception as e:
        print(f"AI 브리핑 생성 중 오류 발생: {e}")
        return None
    





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

def update_sent_links(links):
    """링크 목록을 send_links.txt파일에 추가"""
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
    except Exception as e:
        print(f"sent_links.txt 파일 로딩 중 오류 발생: {e}")
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
        'https://www.hankyung.com/feed/it',
        'https://www.bloter.net/rss',
        'https://www.ciokorea.com/rss',
        'https://rss.mt.co.kr/mt_all.xml',
        'https://www.ddaily.co.kr/rss.xml'
    ]
    
    found_news = []
    unique_links = set()
    print("뉴스 수집을 시작합니다...")
    for url in rss_feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if entry.link in sent_links or entry.link in unique_links:
                    continue
                
                search_text = entry.title + " " + entry.get('summary', '')
                keywords = [
                    '생성형 AI', 'LLM', 'Gemini', 'ChatGPT', '인공지능 윤리', 'AI 반도체',
                    '증시', '코스피', '나스닥', '반도체', '테마주', '금리', '실적 발표',
                    '딥러닝', '강화학습', '데이터 과학', '컴퓨터 비전', '자연어 처리', 'NLP'
                ]
                for keyword in keywords:
                    if keyword.lower() in search_text.lower():
                        summary_html = entry.get('summary', '요약 없음')
                        soup = BeautifulSoup(summary_html, 'lxml')
                        summary_text = soup.get_text(strip=True)
                        image_url = get_image_from_url(entry.link)
                        news_item = {
                            'title': entry.title, 'link': entry.link,
                            'summary': summary_text[:150] + '...', 'image_url': image_url
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
    # 템플릿에 ai_briefing 변수를 전달
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

# --- main 실행 부분 ---
if __name__ == "__main__":
    RECEIVER_EMAIL = "rjh@ylp.co.kr"
    
    news_data = get_news_from_rss()
    
    if news_data:
        # 1. AI 브리핑 생성
        news_titles = [news['title'] for news in news_data]
        ai_briefing = generate_ai_briefing(news_titles)
        
        # 2. 이메일 본문 생성 (AI 브리핑 전달)
        email_body = create_email_html(news_data, ai_briefing)

        email_subject = f"[{datetime.now().strftime('%Y-%m-%d')}] 오늘의 AI/주식/머신러닝 뉴스"
        send_email_oauth(RECEIVER_EMAIL, email_subject, email_body)
        
        new_links_to_save = [news['link'] for news in news_data]
        update_sent_links(new_links_to_save)
    else:
        print("발송할 새로운 뉴스가 없습니다.")

# (get_news_from_rss, update_sent_links, send_email_oauth 등 다른 함수는 기존과 동일합니다.)
# (위 코드에서는 생략되었지만, 실제 파일에서는 그대로 유지해야 합니다.)


