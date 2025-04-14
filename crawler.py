from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from multiprocessing import Pool
from db_handler import insert_product_data
import csv
import re

class DanawaCrawler:
    def __init__(self):
        self.errorList = list()
        self.crawlingCategory = list()

        # CSV에서 카테고리 정보 읽기
        with open('CrawlingCategory.csv', 'r', newline='') as file:
            for crawlingValues in csv.reader(file, skipinitialspace=True):
                if not crawlingValues[0].startswith("//"):
                    self.crawlingCategory.append({
                        'name': crawlingValues[0],
                        'url': crawlingValues[1],
                        'crawlingPageSize': int(crawlingValues[2])
                    })

    def start_crawling(self):
        # 멀티프로세스를 사용하여 카테고리 별로 크롤링
        pool = Pool(processes=2)
        pool.map(self.crawl_category, self.crawlingCategory)
        pool.close()
        pool.join()

    def clean_price(self, price):
        # 가격 문자열을 숫자로 변환하고 오류가 발생하지 않도록 예외 처리
        try:
            cleaned_price = re.sub(r'[^0-9]', '', price)
            return int(cleaned_price)
        except ValueError:
            print(f"Error cleaning price: {price}")
            return None

    def crawl_category(self, categoryValue):
        category_name = categoryValue['name']
        category_url = categoryValue['url']
        crawling_size = categoryValue['crawlingPageSize']

        print(f'Crawling Start : {category_name}')

        # 크롬 드라이버 초기화
        browser = self.init_browser()

        browser.get(category_url)

        # 페이지 로딩 대기
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.XPATH, '//option[@value="90"]')))
        browser.find_element(By.XPATH, '//option[@value="90"]').click()

        try:
            # 크롤링 데이터 저장용 CSV 파일
            with open(f'{category_name}.csv', 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(['Product ID', 'Product Name', 'Price', 'Product URL'])

                for page in range(1, crawling_size + 1):
                    if page > 1:
                        # 페이지 이동
                        next_button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.XPATH, '//a[@class="next"]')))
                        next_button.click()

                    # 상품 목록 추출
                    products = browser.find_elements(By.XPATH, '//ul[@class="product_list"]/li')
                    for product in products:
                        try:
                            product_id = product.get_attribute('id')[11:]
                            product_name = product.find_element(By.XPATH, './div/div[2]/p/a').text.strip()
                            price_str = product.find_element(By.XPATH, './div/div[3]/ul/li/p[2]/a/strong').text.strip()
                            price = self.clean_price(price_str)

                            if price is not None:
                                product_url = product.find_element(By.XPATH, './div/div[2]/p/a').get_attribute('href')

                                # DB에 데이터 삽입
                                insert_product_data(product_id, product_name, category_name, price, product_url)
                                writer.writerow([product_id, product_name, price, product_url])
                            else:
                                print(f"Invalid price data for product ID: {product_id}")
                        except Exception as e:
                            print(f'Error processing product: {e}')

        except Exception as e:
            print(f'Error in crawling category {category_name}: {e}')
            self.errorList.append(category_name)
        finally:
            browser.quit()
            print(f'Crawling Finish : {category_name}')

    def init_browser(self):
        # Service 객체로 크롬 드라이버 경로 지정
        service = Service(executable_path=r'C:\Users\ryan\python_project\chromedriver-win64\chromedriver.exe')
        return webdriver.Chrome(service=service)

if __name__ == '__main__':
    crawler = DanawaCrawler()
    crawler.start_crawling()
