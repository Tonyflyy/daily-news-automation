import os
import base64
import markdown
import json
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
        아래 뉴스 목록을 분석하여, 독자를 위한 매우 간결하고 읽기 쉬운 '데일리 브리핑'을 작성해주세요.

        **출력 형식 규칙:**
        1. '에디터 브리핑'은 '## 에디터 브리핑' 헤더로 시작하며, 오늘 뉴스의 핵심을 2~3 문장으로 요약합니다.
        2. '주요 뉴스 분석'은 '## 주요 뉴스 분석' 헤더로 시작합니다.
        3. 주요 뉴스 분석에서는 가장 중요한 뉴스 카테고리 2~3개를 '###' 헤더로 구분합니다.
        4. 각 카테고리 안에서는, 관련된 여러 뉴스를 **하나의 간결한 문장으로 요약**하고 글머리 기호(`*`)를 사용합니다.
        5. 문장 안에서 강조하고 싶은 특정 키워드는 굵은 글씨 대신 **큰따옴표(" ")**로 묶어주세요.

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

# --- 새로 추가된 AI 뉴스 선별 함수 ---
def select_top_news_with_ai(news_list):
    """
    전체 뉴스 목록을 Gemini API에 보내 가장 중요한 Top 10 뉴스를 선별합니다.
    """
    print(f"AI 뉴스 큐레이션을 시작합니다... (대상: {len(news_list)}개)")
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("GEMINI_API_KEY가 설정되지 않았습니다.")
            return news_list[:10] # AI를 사용할 수 없으면 그냥 앞 10개를 반환

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # AI에게 전달할 뉴스 정보를 가공합니다.
        news_context_for_selection = ""
        for i, news in enumerate(news_list):
            news_context_for_selection += f"기사 #{i}:\n제목: {news['title']}\n요약: {news['summary']}\n\n"

        # AI에게 뉴스 선별을 지시하는 프롬프트
        prompt = f"""
        당신은 한국의 IT/경제 분야를 다루는 전문 뉴스 편집장입니다.
        아래는 오늘 수집된 뉴스 기사 목록입니다. 각 기사에는 고유한 번호(#)가 있습니다.

        당신의 임무는 이 모든 기사를 검토하여, 오늘 독자들이 반드시 알아야 할 **가장 중요하고 영향력 있는 기사 10개**를 선별하는 것입니다.
        시장 동향, 기술 혁신, 주요 기업 소식 등을 종합적으로 고려하여 순위를 매겨주세요.

        **출력 형식 규칙:**
        - 반드시 JSON 형식으로 응답해야 합니다.
        - JSON 객체는 'top_10_indices'라는 키를 가져야 합니다.
        - 'top_10_indices'의 값은 당신이 선택한 가장 중요한 기사 10개의 '번호'를 담은 숫자 배열(array)이어야 합니다. 예: [3, 15, 4, ...].

        [오늘의 뉴스 목록]
        {news_context_for_selection}
        """

        response = model.generate_content(prompt)
        # AI의 응답에서 JSON 부분만 추출
        json_response_text = response.text.strip().replace("```json", "").replace("```", "")
        selected_data = json.loads(json_response_text)
        
        selected_indices = selected_data.get('top_10_indices', [])
        
        # 선택된 인덱스에 해당하는 뉴스만 골라서 새로운 리스트를 만듭니다.
        top_10_news = [news_list[i] for i in selected_indices if i < len(news_list)]

        print(f"AI가 {len(top_10_news)}개의 Top 뉴스를 선별했습니다.")
        return top_10_news

    except Exception as e:
        print(f"AI 뉴스 큐레이션 중 오류 발생: {e}")
        # 오류 발생 시에도 시스템이 멈추지 않도록 그냥 앞 10개 뉴스를 반환
        return news_list[:10]

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

def send_email_oauth(sender_email, receiver_emails, subject, body):
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
        message['To'] = ", ".join(receiver_emails)
        message['From'] = sender_email
        message['Subject'] = subject
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}
        send_message = (service.users().messages().send(userId="me", body=create_message).execute())
        print(f"메시지 ID: {send_message['id']} 이메일 발송 성공! (수신자: {', '.join(receiver_emails)})")
    except HttpError as error:
        print(f"이메일 발송 중 오류 발생: {error}")

# --- 새로 추가된 슬랙 메시지 발송 함수 ---
def send_to_slack(webhook_url, news_list, ai_briefing):
    """
    뉴스레터 내용을 Slack의 Block Kit 형식으로 만들어 Webhook으로 전송합니다.
    """
    if not webhook_url:
        print("슬랙 Webhook URL이 설정되지 않았습니다.")
        return

    print("슬랙으로 뉴스레터 발송을 시작합니다...")
    
    # 슬랙 메시지 헤더
    today_str = datetime.now().strftime("%Y-%m-%d")
    header_text = f"📰 오늘의 AI/주식/머신러닝 Top {len(news_list)} 뉴스 ({today_str})"
    
    # 슬랙 메시지 본문(블록) 구성
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header_text, "emoji": True}},
    ]
    
    # AI 브리핑이 있으면 추가
    if ai_briefing:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*🤖 오늘의 브리핑*\n{ai_briefing}"}})
        blocks.append({"type": "divider"})

    # 뉴스 목록 추가
    for news in news_list:
        news_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{news['link']}|{news['title']}>*\n{news['summary']}"
            }
        }
        # 이미지가 있으면 썸네일로 추가
        if news.get('image_url'):
            news_block["accessory"] = {
                "type": "image",
                "image_url": news['image_url'],
                "alt_text": "Article thumbnail"
            }
        blocks.append(news_block)
        blocks.append({"type": "divider"})

    payload = {"blocks": blocks}

    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        print("슬랙 메시지 발송 성공!")
    except Exception as e:
        print(f"슬랙 메시지 발송 중 오류 발생: {e}")

if __name__ == "__main__":
    recipients_str = os.getenv('RECIPIENT_LIST', 'rjh@ylp.co.kr')
    recipient_list = [email.strip() for email in recipients_str.split(',')]
    SENDER_EMAIL = "zzzfbwnsgh@gmail.com"
    SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL') # 슬랙 URL 불러오기
    
    # 1. 일단 모든 뉴스를 수집합니다.
    all_news_data = get_news_from_rss()
    
    if all_news_data:
        # 2. AI를 사용해 Top 10 뉴스를 선별합니다.
        top_news_data = select_top_news_with_ai(all_news_data)

        # 3. 선별된 Top 10 뉴스를 바탕으로 AI 브리핑을 생성합니다.
        ai_briefing_markdown = generate_ai_briefing(top_news_data)
        ai_briefing_html = markdown.markdown(ai_briefing_markdown) if ai_briefing_markdown else None
        
        # 4. 최종 10개의 뉴스와 브리핑으로 이메일 본문을 만듭니다.
        email_body = create_email_html(top_news_data, ai_briefing_html)
        email_subject = f"[{datetime.now().strftime('%Y-%m-%d')}] 오늘의 AI/주식/머신러닝 Top 10 뉴스"
        send_email_oauth(SENDER_EMAIL, recipient_list, email_subject, email_body)

        # 슬랙 발송 (마크다운 원본을 전달)
        send_to_slack(SLACK_WEBHOOK_URL, top_news_data, ai_briefing_markdown)
        
        # 5. 발송된 10개 뉴스의 링크만 기록합니다.
        new_links_to_save = [news['link'] for news in top_news_data]
        update_sent_links(new_links_to_save)
    else:
        print("발송할 새로운 뉴스가 없습니다.")



