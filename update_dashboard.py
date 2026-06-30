import os
import datetime
import requests
from bs4 import BeautifulSoup

# 환경 변수에서 GitHub Secrets에 저장한 RapidAPI 키 로드
RAPID_KEY = os.environ.get("RAPIDAPI_KEY")

# ==========================================
# PART 1: 구글 금융 환율 크롤링
# ==========================================
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

def get_google_finance_rate(currency_code):
    url = f"https://www.google.com/finance/quote/{currency_code}-KRW"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        rate_element = soup.select_one(".YMl32s")
        if rate_element:
            return rate_element.text.strip()
        return "0.00"
    except:
        return "0.00"

usd_rate = get_google_finance_rate("USD")
jpy_rate = get_google_finance_rate("JPY")
eur_rate = get_google_finance_rate("EUR")

if jpy_rate != "0.00":
    try:
        jpy_float = float(jpy_rate.replace(",", "")) * 100
        jpy_rate = f"{jpy_float:,.2f}"
    except: pass

print(f"📌 [환율 수집 완료] USD: {usd_rate} | JPY(100엔): {jpy_rate} | EUR: {eur_rate}")


# ==========================================
# PART 2: Skyscanner(RapidAPI) 실시간 항공권 트렌드 수집
# ==========================================
def get_skyscanner_trends(origin, destination):
    """스카이스캐너 API를 통해 특정 노선의 향후 6개월간 월별 최저가를 가져옵니다."""
    if not RAPID_KEY:
        print("⚠️ RAPIDAPI_KEY 환경변수가 설정되지 않았습니다.")
        return {}

    # Skyscanner Browse Cache / Flexible Prices 엔드포인트 활용
    url = "https://skyscanner-flights.p.rapidapi.com/v1/flights/browse-chapest-prices"
    
    today = datetime.date.today()
    trends = {}
    
    # 오늘 기준 향후 6개월의 년-월(YYYY-MM) 계산
    for i in range(1, 7):
        future_date = today + datetime.timedelta(days=i * 30)
        ym = future_date.strftime("%Y-%m")
        
        # 각 월별 최저가 조회 쿼리 송신
        querystring = {
            "origin": origin,
            "destination": destination,
            "departureDate": ym,
            "currency": "KRW"
        }
        api_headers = {
            "X-RapidAPI-Key": RAPID_KEY,
            "X-RapidAPI-Host": "skyscanner-flights.p.rapidapi.com"
        }
        
        try:
            res = requests.get(url, headers=api_headers, params=querystring, timeout=10)
            if res.status_code == 200:
                # 결과 리스트 중 가장 최상단 최저가 파싱
                price_data = res.json().get("content", {}).get("cheapestPrice", 0)
                trends[ym] = int(price_data) if price_data else 0
            else:
                trends[ym] = 0
        except:
            trends[ym] = 0
            
    return trends

# 스카이스캐너 데이터 엔진 가동
tokyo_trends = get_skyscanner_trends("ICN", "NRT")
helsinki_trends = get_skyscanner_trends("ICN", "HEL")

print(f"📌 [항공권 트렌드 수집 완료] 도쿄: {tokyo_trends} | 헬싱키: {helsinki_trends}")


# ==========================================
# PART 3: HTML 대시보드(index.html) 업데이트 및 동적 가공
# ==========================================
html_file_path = "index.html"

if os.path.exists(html_file_path):
    with open(html_file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
        
    # 1. 환율 정보 갱신
    currency_names = soup.find_all("div", class_="currency-name")
    for name_div in currency_names:
        text = name_div.text.strip()
        rate_div = name_div.find_next_sibling("div", class_="currency-rate")
        if rate_div:
            if "미국 달러" in text and usd_rate != "0.00": rate_div.string = f"{usd_rate} 원"
            elif "일본 엔화" in text and jpy_rate != "0.00": rate_div.string = f"{jpy_rate} 원"
            elif "유로화" in text and eur_rate != "0.00": rate_div.string = f"{eur_rate} 원"

    # 2. 항공권 그래프 갱신 함수
    def update_html_chart(route_index, trends_data):
        if not trends_data or all(v == 0 for v in trends_data.values()):
            return
        
        valid_prices = [v for v in trends_data.values() if v > 0]
        if not valid_prices: return
        max_p = max(valid_prices)
        min_p = min(valid_prices)
        
        routes = soup.find_all("div", class_="flight-route")
        if len(routes) > route_index:
            target_route = routes[route_index]
            
            summary_span = target_route.select_one(".price-trend-summary span")
            if summary_span:
                min_month_str = [k for k, v in trends_data.items() if v == min_p][0]
                summary_span.string = f"{int(min_month_str.split('-')[1])}월 ({min_p:,}원)"
            
            bars = target_route.select(".chart-bar-wrapper")
            for idx, (ym, price) in enumerate(trends_data.items()):
                if idx < len(bars) and price > 0:
                    bar_div = bars[idx].select_one(".chart-bar")
                    label_div = bars[idx].select_one(".chart-label")
                    price_label = bars[idx].select_one(".bar-price-label")
                    
                    if label_div: label_div.string = f"{int(ym.split('-')[1])}월"
                    if price_label: price_label.string = f"{int(price/10000)}만"
                    if bar_div:
                        bar_div["data-price"] = f"{price:,}원"
                        # 최저 45% ~ 최고 95% 비율 환산 스케일링
                        height_percent = int(45 + (price / max_p) * 50)
                        bar_div["style"] = f"height: {height_percent}%;"
                        
                        if price == min_p:
                            bar_div["class"] = "chart-bar lowest"
                        else:
                            bar_div["class"] = "chart-bar"

    # 차트 업데이트 반영
    update_html_chart(0, tokyo_trends)
    update_html_chart(1, helsinki_trends)

    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(str(soup.prettify(formatter="html")))
    print("🎉 [스카이스캐너 마그네틱 연동 성공] 환율 및 최저가 데이터 반영 완료!")
