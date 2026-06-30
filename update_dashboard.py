import os
import datetime
import requests
from bs4 import BeautifulSoup

RAPID_KEY = os.environ.get("RAPIDAPI_KEY")

# ==========================================
# [스마트 주기 제어] 한국 시간 기준 현재 시간 계산
# ==========================================
utc_now = datetime.datetime.now(datetime.timezone.utc)
kst_now = utc_now + datetime.timedelta(hours=9)
current_hour = kst_now.hour

# 낮 12시인지 판정
is_flight_update_time = (current_hour == 12)

print(f"⏰ [시간 검증] 현재 한국 시간: {kst_now.strftime('%Y-%m-%d %H:%M:%S')}")
if not is_flight_update_time:
    print("💤 현재 시간은 항공권 업데이트 시간이 아닙니다. (낮 12시에 가동)")
    exit() # 12시가 아니면 즉시 종료하여 불필요한 연산 방지

# ==========================================
# 1. Skyscanner 항공권 최저가 수집 (낮 12시에만 가동)
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

print("🚀 낮 12시 조건 충족! 스카이스캐너 라이브 항공권 수집을 시작합니다.")
tokyo_trends = get_skyscanner_trends("ICN", "NRT")
helsinki_trends = get_skyscanner_trends("ICN", "HEL")


# ==========================================
# 2. HTML 항공권 차트 갱신 연동
# ==========================================
html_file_path = "index.html"

if os.path.exists(html_file_path):
    with open(html_file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

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

    update_html_chart("도쿄", tokyo_trends)
    update_html_chart("헬싱키", helsinki_trends)

    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(str(soup.prettify(formatter="html")))
    print("🎉 [백엔드 작업 완수] 항공권 최저가 트렌드 차트가 index.html에 동기화되었습니다.")
