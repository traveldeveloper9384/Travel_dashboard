import os
import datetime
import requests
from bs4 import BeautifulSoup

RAPID_KEY = os.environ.get("RAPIDAPI_KEY")

# ==========================================
# [스마트 주기 제어] 한국 시간 기준 현재 시간 계산
# ==========================================
# GitHub Actions 서버는 기본적으로 UTC(영국) 기준시를 사용하므로, 
# 9시간을 더해 정확한 한국 표준시(KST)를 구합니다.
utc_now = datetime.datetime.now(datetime.timezone.utc)
kst_now = utc_now + datetime.timedelta(hours=9)
current_hour = kst_now.hour

# 💡 목표: 한국 시간 기준 "낮 12시" 부근일 때만 항공권 수집 활성화
# GitHub Actions의 미세한 실행 오차를 감안하여 12시 정각이 포함된 시간대에 작동하도록 설정합니다.
is_flight_update_time = (current_hour == 12)

print(f"⏰ [시간 검증] 현재 한국 시간: {kst_now.strftime('%Y-%m-%d %H:%M:%S')} (시각: {current_hour}시)")
if is_flight_update_time:
    print("🚀 [조건 충족] 낮 12시이므로 오늘자 실시간 항공권 업데이트를 진행합니다.")
else:
    print("💤 [조건 미충족] 항공권은 낮 12시에 업데이트됩니다. 오늘은 기존 수치를 유지하고 환율만 갱신합니다.")


# ==========================================
# 1. 구글 금융 환율 크롤링 (매 30분마다 항상 실행)
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

print(f"📌 [환율 수집] USD: {usd_rate} | JPY(100엔): {jpy_rate} | EUR: {eur_rate}")


# ==========================================
# 2. Skyscanner 항공권 최저가 수집 (하루 한 번 분기 제어)
# ==========================================
def get_skyscanner_trends(origin, destination):
    if not RAPID_KEY:
        return {}
    url = "https://skyscanner-flights.p.rapidapi.com/v1/flights/browse-chapest-prices"
    today = datetime.date.today()
    trends = {}
    
    for i in range(1, 7):
        future_date = today + datetime.timedelta(days=i * 30)
        ym = future_date.strftime("%Y-%m")
        querystring = {"origin": origin, "destination": destination, "departureDate": ym, "currency": "KRW"}
        api_headers = {"X-RapidAPI-Key": RAPID_KEY, "X-RapidAPI-Host": "skyscanner-flights.p.rapidapi.com"}
        try:
            res = requests.get(url, headers=api_headers, params=querystring, timeout=10)
            if res.status_code == 200:
                price_data = res.json().get("content", {}).get("cheapestPrice", 0)
                trends[ym] = int(price_data) if price_data else 0
            else: trends[ym] = 0
        except: trends[ym] = 0
    return trends

# 조건부 호출: 낮 12시 타임라인일 때만 API 호출, 그 외 시간엔 빈 딕셔너리 반환
tokyo_trends = get_skyscanner_trends("ICN", "NRT") if is_flight_update_time else {}
helsinki_trends = get_skyscanner_trends("ICN", "HEL") if is_flight_update_time else {}

if is_flight_update_time:
    print(f"📌 [항공권 라이브 수집] 도쿄: {tokyo_trends} | 헬싱키: {helsinki_trends}")


# ==========================================
# 3. HTML 데이터 업데이트 (index.html)
# ==========================================
html_file_path = "index.html"

if os.path.exists(html_file_path):
    with open(html_file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
        
    # 환율 정보 무조건 업데이트
    currency_names = soup.find_all("div", class_="currency-name")
    for name_div in currency_names:
        text = name_div.text.strip()
        rate_div = name_div.find_next_sibling("div", class_="currency-rate")
        if rate_div:
            if "미국 달러" in text and usd_rate != "0.00": rate_div.string = f"{usd_rate} 원"
            elif "일본 엔화" in text and jpy_rate != "0.00": rate_div.string = f"{jpy_rate} 원"
            elif "유로화" in text and eur_rate != "0.00": rate_div.string = f"{eur_rate} 원"

    # 항공권 정보 업데이트 (낮 12시에 수집된 데이터가 있을 때만 HTML 그래프 구조 변형)
    def update_html_chart(route_title_keyword, trends_data):
        if not trends_data or all(v == 0 for v in trends_data.values()): return
        valid_prices = [v for v in trends_data.values() if v > 0]
        if not valid_prices: return
        max_p, min_p = max(valid_prices), min(valid_prices)
        
        routes = soup.find_all("div", class_="flight-route")
        for route in routes:
            title_span = route.select_one(".route-title")
            if title_span and route_title_keyword in title_span.text:
                summary_span = route.select_one(".price-trend-summary span")
                if summary_span:
                    min_month_str = [k for k, v in trends_data.items() if v == min_p][0]
                    summary_span.string = f"{int(min_month_str.split('-')[1])}월 ({min_p:,}원)"
                
                bars = route.select(".chart-bar-wrapper")
                for idx, (ym, price) in enumerate(trends_data.items()):
                    if idx < len(bars) and price > 0:
                        bar_div = bars[idx].select_one(".chart-bar")
                        label_div = bars[idx].select_one(".chart-label")
                        price_label = bars[idx].select_one(".bar-price-label")
                        
                        if label_div: label_div.string = f"{int(ym.split('-')[1])}월"
                        if price_label: price_label.string = f"{int(price/10000)}만"
                        if bar_div:
                            bar_div["data-price"] = f"{price:,}원"
                            height_percent = int(35 + (price / max_p) * 60)
                            bar_div["style"] = f"height: {height_percent}%;"
                            bar_div["class"] = "chart-bar lowest" if price == min_p else "chart-bar"

    if is_flight_update_time:
        update_html_chart("도쿄", tokyo_trends)
        update_html_chart("헬싱키", helsinki_trends)

    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(str(soup.prettify(formatter="html")))
    print("🎉 [작업 완료] 환율 및 조건별 항공권 업데이트가 완벽히 처리되었습니다.")
