import os
import base64
import markdown 
from email.mime.text import MIMEText
from urllib.parse import urljoin, urlparse, quote
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
from datetime import datetime, timedelta
import requests

# --- AI 브리핑 생성 함수 ---
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

# --- 링크 기록 업데이트 함수 ---
def update_sent_links(links):
    try:
        with open('sent_links.txt', 'a', encoding='utf-8') as f:
            for link in links:
                f.write(link + '\n')
        print(f"{len(links)}개의 새 링크를 sent_links.txt에 추가했습니다.")
    except Exception as e:
        print(f"sent_links.txt 파일 업데이트 중 오류 발생: {e}")


def get_news_from_api():
    sent_links = set()
    try:
        with open('sent_links.txt', 'r', encoding='utf-8') as f:
            sent_links = set(line.strip() for line in f)
        print(f"총 {len(sent_links)}개의 보낸 기록을 sent_links.txt에서 불러왔습니다.")
    except FileNotFoundError:
        print("sent_links.txt 파일을 찾을 수 없어, 새로운 기록을 시작합니다.")
    
    api_key = os.getenv('GNEWS_API_KEY')
    if not api_key:
        print("GNEWS_API_KEY가 설정되지 않았습니다.")
        return []

    # --- 이 부분이 개선되었습니다 ---
    # 1. 키워드 확장 및 검색 쿼리 형식 변경
    keywords = ["AI", "인공지능", "반도체", "주식", "증시", "머신러닝", "딥러닝", "LLM"]
    query = " OR ".join(f'"{k}"' for k in keywords) # 각 키워드를 큰따옴표로 묶어 정확도 향상

    # 2. 어제 날짜 계산 (ISO 8601 형식)
    yesterday = datetime.now() - timedelta(days=1)
    from_time = yesterday.strftime('%Y-%m-%dT%H:%M:%SZ')

    # 3. API 요청 URL에 새로운 파라미터 추가
    url = (f'https://gnews.io/api/v4/search?'
           f'q={query}&'
           f'lang=ko&'
           f'country=kr&'
           f'max=25&'
           f'in=title&'             # '제목'에서만 검색하도록 지정
           f'from={from_time}&'      # '어제'부터 검색하도록 지정
           f'apikey={api_key}')
    # --- 여기까지 ---
    
    found_news = []
    print("GNews API를 통해 뉴스 수집을 시작합니다...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        articles = data.get('articles', [])

        for article in articles:
            link = article['url']
            if link in sent_links:
                continue
            
            image_url = get_image_from_url(link)
            news_item = {
                'title': article['title'],
                'link': link,
                'summary': article['description'][:150] + '...' if article.get('description') else '',
                'image_url': image_url
            }
            found_news.append(news_item)

    except Exception as e:
        print(f"GNews API 요청 중 오류 발생: {e}")

    print(f"총 {len(found_news)}개의 새로운 뉴스를 찾았습니다.")
    return found_news

def get_news_from_rss():
    rss_feeds = [
        'https://news.naver.com/main/rss.naver?sid1=105',  # IT/과학
        'https://news.naver.com/main/rss.naver?sid1=101',  # 경제
    ]
    
    print("--- [최종 디버깅 모드] ---")
    print("RSS 피드에서 각 피드별 첫 3개 기사의 실제 내용을 확인합니다.")

    for url in rss_feeds:
        print(f"\n\n--- 피드 주소: {url} ---")
        try:
            feed = feedparser.parse(url, agent='Mozilla/5.0')
            
            if not feed.entries:
                print(">> 이 피드에서 기사를 찾지 못했습니다. 피드가 비어있거나 차단되었을 수 있습니다.")
                continue

            # 각 피드의 첫 3개 기사만 확인
            for i, entry in enumerate(feed.entries[:3]):
                summary_html = entry.get('summary', '요약 없음')
                soup = BeautifulSoup(summary_html, 'lxml')
                summary_text = soup.get_text(strip=True)
                
                search_text = entry.title + " " + summary_text
                
                print(f"\n--- 기사 #{i+1} ---")
                print(f"제목: {entry.title}")
                print(f"검색 대상 텍스트 (앞 300자): {search_text[:300]}...")
        
        except Exception as e:
            print(f"'{url}' 피드 처리 중 심각한 오류 발생: {e}")
    
    print("\n--- [디버깅 완료] ---")
    # 디버깅 중에는 이메일을 보내지 않도록 의도적으로 빈 리스트를 반환합니다.
    return []

def get_news_from_naver_api():
    sent_links = set()
    try:
        with open('sent_links.txt', 'r', encoding='utf-8') as f:
            sent_links = set(line.strip() for line in f)
        print(f"총 {len(sent_links)}개의 보낸 기록을 sent_links.txt에서 불러왔습니다.")
    except FileNotFoundError:
        print("sent_links.txt 파일을 찾을 수 없어, 새로운 기록을 시작합니다.")

    client_id = os.getenv('NAVER_CLIENT_ID')
    client_secret = os.getenv('NAVER_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("네이버 API 키가 설정되지 않았습니다.")
        return []

    keywords = ["AI", "인공지능", "반도체", "주식", "증시", "머신러닝", "딥러닝", "LLM", "삼성전자", "엔비디아"]
    query = " OR ".join(keywords)
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    # API는 하루치 검색(date)을 지원하지 않으므로, 최신순(sim)으로 100개를 요청하여 필터링
    url = f"https://openapi.naver.com/v1/search/news.json?query={quote(query)}&display=100&sort=sim"

    found_news = []
    print("네이버 검색 API를 통해 뉴스 수집을 시작합니다...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        articles = data.get('items', [])

        for article in articles:
            # 네이버 뉴스가 아닌 링크(예: 연예뉴스)는 건너뛰기
            if "n.news.naver.com" not in article['link']:
                continue
            
            link = article['originallink'] # 원본 기사 링크
            if link in sent_links:
                continue

            # API가 돌려주는 HTML 태그(<b>)를 제거
            soup_title = BeautifulSoup(article['title'], 'html.parser')
            clean_title = soup_title.get_text(strip=True)
            soup_desc = BeautifulSoup(article['description'], 'html.parser')
            clean_desc = soup_desc.get_text(strip=True)

            image_url = get_image_from_url(link)
            news_item = {
                'title': clean_title,
                'link': link,
                'summary': clean_desc[:150] + '...',
                'image_url': image_url
            }
            found_news.append(news_item)
            
    except Exception as e:
        print(f"네이버 API 요청 중 오류 발생: {e}")

    print(f"총 {len(found_news)}개의 새로운 뉴스를 찾았습니다.")
    return found_news
    

# --- 이메일 생성 및 발송 함수 ---
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

# --- 메인 실행 ---
if __name__ == "__main__":
    RECEIVER_EMAIL = "rjh@ylp.co.kr"
    #news_data = get_news_from_api()
    news_data = get_news_from_naver_api()
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









