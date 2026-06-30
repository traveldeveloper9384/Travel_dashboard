import os
import requests
from bs4 import BeautifulSoup

# 크롤링 차단을 예방하기 위한 헤더 설정 (구글은 언어 설정을 주면 더 정확합니다)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_google_finance_rate(currency_code):
    """구글 금융에서 특정 통화의 원화(KRW) 환율을 가져옵니다."""
    url = f"https://www.google.com/finance/quote/{currency_code}-KRW"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # 구글 금융의 실시간 가격 데이터가 담기는 고유 클래스명(YMl32s) 추출
        # 구글은 전 세계 동일하게 이 클래스를 사용하여 가격을 표시합니다.
        rate_element = soup.select_one(".YMl32s")

        if rate_element:
            rate_text = rate_element.text.strip()
            # 쉼표(,)나 불필요한 문자가 있으면 정제 (예: 1,382.50 -> 1,382.50)
            return rate_text
        return "0.00"
    except Exception as e:
        print(f"⚠️ {currency_code} 환율 구글 크롤링 실패: {e}")
        return "0.00"


# 1. 구글 금융에서 실시간 환율 수집
usd_rate = get_google_finance_rate("USD")
jpy_rate = get_google_finance_rate("JPY")
eur_rate = get_google_finance_rate("EUR")

# 💡 중요: 구글 금융에서 엔화(JPY)는 '1엔' 기준으로 나옵니다.
# 대시보드는 '100엔' 기준(예: 885원)으로 설계되어 있으므로, 100을 곱해 단위를 맞춰줍니다.
if jpy_rate != "0.00":
    try:
        # 천의 자리에 쉼표가 있을 수 있으므로 제거 후 계산
        jpy_float = float(jpy_rate.replace(",", "")) * 100
        # 대시보드 서식에 맞춰 소수점 2자리와 쉼표를 다시 붙여줌
        jpy_rate = f"{jpy_float:,.2f}"
    except Exception as e:
        print(f"⚠️ JPY 단위 변환 실패: {e}")

print(
    f"📌 [구글 수집 결과] USD: {usd_rate}원 | JPY(100엔): {jpy_rate}원 | EUR: {eur_rate}원"
)


# 2. 대시보드 HTML 파일 (index.html) 업데이트
html_file_path = "index.html"

if not os.path.exists(html_file_path):
    print(
        f"❌ '{html_file_path}' 파일을 찾을 수 없습니다. 경로를 확인해주세요."
    )
    exit()

try:
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    dashboard_soup = BeautifulSoup(html_content, "html.parser")
    currency_names = dashboard_soup.find_all("div", class_="currency-name")
    is_updated = False

    for name_div in currency_names:
        text_content = name_div.text.strip()
        rate_div = name_div.find_next_sibling("div", class_="currency-rate")

        if rate_div:
            if "미국 달러" in text_content and usd_rate != "0.00":
                rate_div.string = f"{usd_rate} 원"
                is_updated = True
            elif "일본 엔화" in text_content and jpy_rate != "0.00":
                rate_div.string = f"{jpy_rate} 원"
                is_updated = True
            elif "유로화" in text_content and eur_rate != "0.00":
                rate_div.string = f"{eur_rate} 원"
                is_updated = True

    # 3. 변경된 데이터를 파일에 저장
    if is_updated:
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(str(dashboard_soup.prettify(formatter="html")))
        print(
            "🎉 구글 금융 데이터로 index.html 대시보드 덮어쓰기가 완료되었습니다!"
        )
    else:
        print(
            "⚠️ 업데이트를 건너뛰었습니다. 환율 값이 0.00이거나 HTML 태그 구조를 확인하세요."
        )

except Exception as e:
    print(f"❌ 파일 처리 중 오류 발생: {e}")
