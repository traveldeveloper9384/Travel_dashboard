import os
import requests
from bs4 import BeautifulSoup

# 1. 네이버 증권 시장지표 페이지 크롤링 (User-Agent 필수 설정)
url = "https://finance.naver.com/marketindex/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    market_soup = BeautifulSoup(response.text, "html.parser")
except Exception as e:
    print(f"❌ 네이버 금융 페이지 크롤링 실패: {e}")
    exit()


def get_exchange_rate(code):
    """네이버 금융 HTML 구조에서 각 통화의 실시간 환율을 안전하게 추출합니다."""
    try:
        # 네이버 금융 marketindex 화면의 주요 통화 요소 검색
        container = market_soup.find("a", class_=code) or market_soup.select_one(
            f"a.head.{code}"
        )
        if container:
            rate = container.find("span", class_="value").text
            return rate
        return "0.00"
    except Exception:
        return "0.00"


# 실시간 환율 데이터 수집 실행
usd_rate = get_exchange_rate("usd")
jpy_rate = get_exchange_rate("jpy")
eur_rate = get_exchange_rate("eur")

print(
    f"📌 [크롤링 완료] 실시간 환율 -> USD: {usd_rate}원 | JPY: {jpy_rate}원 | EUR: {eur_rate}원"
)


# 2. 대시보드 HTML 파일 (travel.html) 읽어오기 및 DOM 업데이트
html_file_path = "index.html"

if not os.path.exists(html_file_path):
    print(
        f"❌ '{html_file_path}' 파일을 찾을 수 없습니다. 경로를 확인해주세요."
    )
    exit()

try:
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # BeautifulSoup으로 대시보드 구조 파싱
    dashboard_soup = BeautifulSoup(html_content, "html.parser")

    # 대시보드 내 모든 통화 이름 영역 추적
    currency_names = dashboard_soup.find_all("div", class_="currency-name")
    is_updated = False

    for name_div in currency_names:
        text_content = name_div.text.strip()

        # 바로 인접한 형제 노드(currency-rate) 찾기
        rate_div = name_div.find_next_sibling("div", class_="currency-rate")

        if rate_div:
            # 텍스트에 통화명이 포함되어 있고 크롤링 값이 정상(0.00이 아님)일 때 업데이트
            if "미국 달러" in text_content and usd_rate != "0.00":
                rate_div.string = f"{usd_rate} 원"
                is_updated = True
            elif "일본 엔화" in text_content and jpy_rate != "0.00":
                rate_div.string = f"{jpy_rate} 원"
                is_updated = True
            elif "유로화" in text_content and eur_rate != "0.00":
                rate_div.string = f"{eur_rate} 원"
                is_updated = True

    # 3. 변경된 돔(DOM) 데이터를 파일에 완전히 덮어쓰기
    if is_updated:
        with open(html_file_path, "w", encoding="utf-8") as f:
            # formatter="html" 설정을 통해 불필요한 깨짐 방지 및 정렬 유지
            f.write(str(dashboard_soup.prettify(formatter="html")))
        print(
            "🎉 travel.html 대시보드가 성공적으로 실시간 데이터로 업데이트되었습니다!"
        )
    else:
        print("⚠️ 업데이트 대상 항목을 찾지 못했거나 크롤링 값이 올바르지 않습니다.")

except Exception as e:
    print(f"❌ 대시보드 파일 업데이트 중 오류 발생: {e}")
