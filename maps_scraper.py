from ast import Return
import json
import time
import os
import random
import sys
import traceback
import requests
import re
from lxml.html import fromstring
from itertools import cycle
from multiprocessing import Process
from typing import final
from dotenv import load_dotenv
from seleniumwire import webdriver
from seleniumwire.utils import decode
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
import mysql.connector
load_dotenv()

thread_count = 1

if (len(sys.argv) > 1):
    try:
        thread_count = int(sys.argv[1])
    except:
        print('Invalid number for thread count')
        sys.exit(1)


def init():
    class MapsScrapingThread():

        def __init__(self):
            self.driver = None
            self.done = False
            self.daemon = True
            self.mydb = mysql.connector.connect(
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_NAME'),
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci"
            )
            self.cursor = self.mydb.cursor(dictionary=True)
            # self.proxy_pool = cycle(self.get_proxies())
            self.places = []
            self.data = {}
            self.json_data = {}
            # self.proxy = next(self.proxy_pool)

        def get_places(self):
            self.mydb = mysql.connector.connect(
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_NAME'),
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci"
            )
            self.cursor = self.mydb.cursor(dictionary=True)

            self.cursor.execute("""
                SELECT p.*, c.nombre_ciudad, d.nombre_departamento, pa.nombre_pais FROM places p
                JOIN ciudades c on c.idciudad = p.ciudades_idciudad
                JOIN departamentos d on d.iddepartamento = c.departamentos_iddepartamento
                JOIN paises pa on pa.idpais = d.paises_idpais
                LEFT JOIN places_info pi on pi.places_idplace = p.idplace
                WHERE pi.idplace_info IS NULL AND pa.nombre_pais like '%Chile%'
            """)

            places = self.cursor.fetchall()
            random.shuffle(places)

            return places

        def get_proxies(self):
            # url = 'https://free-proxy-list.net/'
            url = 'https://www.sslproxies.org/'
            response = requests.get(url)
            parser = fromstring(response.text)
            proxies = set()
            for i in parser.xpath('//tbody/tr')[:10]:
                if i.xpath('.//td[7][contains(text(),"yes")]'):
                    proxy = ":".join([i.xpath('.//td[1]/text()')[0],
                                      i.xpath('.//td[2]/text()')[0]])
                    proxies.add(proxy)
            return proxies

        def init_driver(self, language='es'):
            if self.driver is not None:
                try:
                    self.driver.close()
                except:
                    pass
            options = webdriver.ChromeOptions()
            # options.add_argument('window-position=-2560,0')
            options.add_experimental_option(
                'prefs', {'intl.accept_languages': 'en-GB' if language == 'en' else 'es-ES'})

            self.driver = webdriver.Chrome(
                chrome_options=options)

        def wait_for_element(self, selector):
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector)))

        def get_json(self):
            self.json_data = {}
            try:
                for request in self.driver.requests:
                    if request.response and 'google.com/search?' in request.url:
                        body = decode(request.response.body, request.response.headers.get(
                            'Content-Encoding', 'identity'))
                        body = (body.decode('utf-8').split("\")]}'\\n")
                                [1].split(']","e')[0] + ']') \
                            .replace('\\/', '/') \
                            .replace('\\\\\\"', '') \
                            .replace('\\"', '"') \
                            .replace('\\', '') \
                            .replace("\\xa0", " ") \

                        self.json_data = json.loads(body)[0][1][0][14]

                    if request.response and 'google.com/maps/preview/place' in request.url:
                        body = decode(request.response.body, request.response.headers.get(
                            'Content-Encoding', 'identity'))

                        body = body.decode('utf-8')[5:]

                        self.json_data = json.loads(body)[6]

            except Exception as e:
                print(e)
                traceback.print_exc()

        def search_place(self, place):
            try:
                input_maps = self.driver.find_element(
                    By.CSS_SELECTOR, 'input[id="searchboxinput"]')
                search_val = f"{place['nombre_place']}, {place['nombre_ciudad']}, {place['nombre_departamento']}, {place['nombre_pais']}"

                action = ActionChains(self.driver)

                action.double_click(input_maps)
                for letter in search_val:
                    action.send_keys(letter)
                action.perform()

                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.sbsb_b .EmLCAe')))

                suggestions = self.driver.find_elements(
                    By.CSS_SELECTOR, '.sbsb_b .EmLCAe')

                match = None

                for suggestion in suggestions:
                    if place['nombre_ciudad'].lower().strip() in suggestion.text.lower().strip():
                        print(place['nombre_ciudad'])
                        match = suggestion
                        break

                    if place['nombre_departamento'].lower().strip() in suggestion.text.lower().strip():
                        print(place['nombre_departamento'])
                        match = suggestion
                        break

                    if place['nombre_pais'].lower().strip() in suggestion.text.lower().strip():
                        print(place['nombre_pais'])
                        match = suggestion
                        break

                if match is not None:
                    print(match.text)
                    match.click()
                    return True

                return False

            except:
                return False

        def get_name(self, lang):
            try:
                self.data[f'nombre_{lang}'] = self.json_data[11]
            except Exception as e:
                print(f'nombre_{lang} not found')
                # print(e)
                # traceback.print_exc()

        def get_direccion(self):
            try:
                self.data[f'direccion'] = self.json_data[2][0]
            except Exception as e:
                print(f'direccion not found')
                # print(e)
                # traceback.print_exc()

        def get_web(self):
            try:
                self.data[f'web'] = self.json_data[7][1]
            except Exception as e:
                print(f'web not found')
                # print(e)
                # traceback.print_exc()

        def get_telefono(self):
            try:
                # element = self.driver.find_elements(
                #     By.CSS_SELECTOR, 'button[data-item-id^="phone:tel:"] .Io6YTe')

                # if len(element) > 0:
                #     element = element[0]
                #     self.data[f'telefono'] = element.text
                self.data[f'telefono'] = self.json_data[178][0][0]
            except Exception as e:
                print(f'telefono not found')
                # print(e)
                # traceback.print_exc()

        def get_horarios(self):
            try:
                element = self.driver.find_elements(
                    By.CSS_SELECTOR, '.LJKBpe-Tswv1b-hour-text')

                if len(element) > 0:
                    element = element[0]
                    element.click()

                    temp = {}

                    days_map = {
                        'lunes': 'monday',
                        'martes': 'tuesday',
                        'miercoles': 'wednesday',
                        'miércoles': 'wednesday',
                        'jueves': 'thursday',
                        'viernes': 'friday',
                        'sabado': 'saturday',
                        'sábado': 'saturday',
                        'domingo': 'sunday',
                        'monday': 'monday',
                        'tuesday': 'tuesday',
                        'wednesday': 'wednesday',
                        'thursday': 'thursday',
                        'friday': 'friday',
                        'saturday': 'saturday',
                        'sunday': 'sunday',
                    }

                    days = self.driver.find_elements(
                        By.CSS_SELECTOR, '.eK4R0e.tfUnhc tr')

                    for day in days:
                        day_name = day.find_element(
                            By.CSS_SELECTOR, '.ylH6lf div:first-child').text.lower().strip()

                        day_times = day.find_elements(
                            By.CSS_SELECTOR, '.mxowUb .G8aQO')
                        day_time = ' - '.join(
                            list(map(lambda x: x.text.lower().strip(), day_times)))

                        temp[days_map[day_name]] = day_time

                    self.data['horarios'] = temp

            except Exception as e:
                print(f'horarios not found')
                # print(e)
                # traceback.print_exc()

        def get_coordenadas(self):
            try:
                self.data['lat'] = self.json_data[9][2]
                self.data['lng'] = self.json_data[9][3]

            except Exception as e:
                print(f'coordenadas not found')
                # print(e)
                # traceback.print_exc()

        def get_rating(self):
            try:
                self.data['rating'] = self.json_data[4][7]

            except Exception as e:
                print(f'rating not found')
                # print(e)
                # traceback.print_exc()

        def get_categorias(self):
            try:
                self.data['categorias'] = list(
                    map(lambda x: x[0], self.json_data[76]))

            except Exception as e:
                print(f'categorias not found')
                # print(e)
                # traceback.print_exc()

        def get_descripcion(self, lang):
            found = False
            try:
                very_long = self.driver.find_element(
                    By.CSS_SELECTOR, '.wEvh0b')
                self.data[f'descripcion_long_{lang}'] = very_long.text
                found = True

            except Exception as e:
                pass
                # print('descripcion not found')

            try:
                self.data[f'descripcion_short_{lang}'] = self.json_data[32][0][1]
                self.data[f'descripcion_long_{lang}'] = self.json_data[32][1][1]
                found = True

            except Exception as e:
                pass
                # print(f'descripcion not found')
                # print(e)
                # traceback.print_exc()

            if not found:
                print('descripcion not found')

        def get_imagenes(self):
            changed_page = False
            try:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.ofKBgf')))

                    element = self.driver.find_elements(
                        By.CSS_SELECTOR, '.ofKBgf')

                    if len(element) > 0:
                        element = element[0]
                        ActionChains(self.driver).move_to_element(
                            element).perform()
                        element.click()

                        changed_page = True
                except:
                    element = self.driver.find_elements(
                        By.CSS_SELECTOR, '.jtJMuf')

                    if len(element) > 0:
                        element = element[0]
                        ActionChains(self.driver).move_to_element(
                            element).perform()
                        element.click()

                        changed_page = True
                    else:
                        raise Exception('not found')

                images = []

                self.wait_for_element(
                    'div[class="onegoogle noprint app-sandbar-vasquette hidden-one-google"]')

                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.m6QErb.DxyBCb')))

                photo_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, '.m6QErb.DxyBCb .mWq4Rd-HiaYvf-MNynB-gevUs')

                if len(photo_elements) == 0:
                    photo_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, '.m6QErb.DxyBCb .U39Pmb')

                for photo in photo_elements:
                    bg_image = photo.value_of_css_property(
                        'background-image')

                    while bg_image == 'url("https://:0/")':
                        ActionChains(self.driver).move_to_element(
                            photo).perform()

                        time.sleep(0.5)
                        bg_image = photo.value_of_css_property(
                            'background-image')

                    bg_image = bg_image.replace(
                        'url(', '').replace(')', '').replace('"', '')
                    url = bg_image.replace('lh5', 'lh3').split('=')[
                        0] + '=s0'
                    images.append(url)

                self.data['imagenes'] = images

            except Exception as e:
                print(f'imagenes not found')
                # print(e)
                # traceback.print_exc()

            finally:
                if changed_page:
                    self.driver.back()
                    self.wait_for_element(
                        'div[class="onegoogle noprint app-sandbar-vasquette"]')

        def get_duracion(self, lang):
            try:
                avg_time_spent = self.json_data[117][0]

                text = avg_time_spent.split(
                    'People typically spend up to ' if lang == 'en' else 'Tiempo máximo de permanencia: ')[1]

                self.data['duracion'] = text.replace("\xa0", " ").replace(
                    "horas", "hour").replace("minuto", "minute")

            except Exception as e:
                print('duracion not found')
                # print(e)
                # traceback.print_exc()

        def get_reviews(self, lang):
            changed_page = False
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'button[jsaction="pane.reviewlist.goToReviews"]')))

                element = self.driver.find_elements(
                    By.CSS_SELECTOR, 'button[jsaction="pane.reviewlist.goToReviews"]')

                if len(element) > 0:
                    element = element[0]
                    ActionChains(self.driver).move_to_element(
                        element).perform()

                    self.driver.execute_script("""
                        var elements = document.querySelectorAll('div[class="m6QErb"][jsan="t-dgE5uNmzjiE,7.m6QErb"]');
                        for (let element of elements) {
                            element.parentNode.removeChild(element);
                        }
                    """)

                    element.click()

                    changed_page = True

                    reviews = []

                    WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'div[class="m6QErb"][jsan="t-dgE5uNmzjiE,7.m6QErb"]')))

                    review_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, 'div[class="m6QErb"][jsan="t-dgE5uNmzjiE,7.m6QErb"] .jftiEf.L6Bbsd')

                    for review in review_elements:
                        ActionChains(self.driver).move_to_element(
                            review).perform()

                        author = review.find_element(
                            By.CSS_SELECTOR, '.d4r55').text.strip()

                        rating = review.find_element(By.CSS_SELECTOR, '.kvMYJc').get_attribute(
                            'aria-label').strip().split('\xa0')[0]

                        more_button = review.find_elements(
                            By.CSS_SELECTOR, '.w8nwRe.kyuRq')
                        if len(more_button) > 0:
                            more_button[0].click()

                        text = review.find_element(
                            By.CSS_SELECTOR, '.wiI7pd').text.strip()

                        reviews.append({
                            'author': author,
                            'rating': rating,
                            'review': text
                        })

                    self.data[f'reviews_{lang}'] = reviews

            except Exception as e:
                print(f'reviews_{lang} not found')
                # print(e)
                # traceback.print_exc()

            finally:
                if changed_page:
                    self.driver.back()
                    self.wait_for_element(
                        'div[class="onegoogle noprint app-sandbar-vasquette"]')

        def scrape(self):
            self.done = False

            self.places = self.get_places()

            for place in self.places:
                self.cursor.execute(
                    f"SELECT * FROM places p JOIN places_info pi on pi.places_idplace = p.idplace WHERE p.idplace = {place['idplace']}")

                is_empty = self.cursor.fetchall()

                if (len(is_empty) > 0):
                    print('place already scraped')
                    continue

                self.data = {
                    'idplace': place['idplace'],
                    'nombre_en': None,
                    'nombre_es': None,
                    'descripcion_short_en': None,
                    'descripcion_short_es': None,
                    'descripcion_long_en': None,
                    'descripcion_long_es': None,
                    'direccion': None,
                    'web': None,
                    'telefono': None,
                    'email': None,
                    'lat': None,
                    'lng': None,
                    'imagenes': {},
                    'duracion': None,
                    'rating': None,
                    'costos': {},
                    'horarios': {},
                    'reviews_en': {},
                    'reviews_es': {},
                    'categorias': {}
                }

                for lang in ['es', 'en']:

                    self.init_driver(lang)
                    self.driver.get('https://www.google.com/maps/')

                    print(f"Scraping {place['nombre_place']} in {lang}")

                    if not self.search_place(place):
                        continue

                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.lMbq3e')))

                    self.get_json()

                    if self.data['direccion'] is None:
                        self.get_direccion()

                    if self.data['web'] is None:
                        self.get_web()

                    if self.data['rating'] is None:
                        self.get_rating()

                    if self.data['telefono'] is None:
                        self.get_telefono()

                    if self.data['horarios'] == {}:
                        self.get_horarios()

                    if self.data['lat'] is None or self.data['lng'] is None:
                        self.get_coordenadas()

                    if self.data['duracion'] is None:
                        self.get_duracion(lang)

                    if self.data['imagenes'] == {}:
                        self.get_imagenes()

                    if self.data['categorias'] == {}:
                        self.get_categorias()

                    self.get_name(lang)
                    self.get_reviews(lang)
                    self.get_descripcion(lang)

                if (self.data['nombre_en'] is None and self.data['nombre_es'] is not None) or (self.data['nombre_en'] is not None and self.data['nombre_es'] is None):
                    raise Exception("Browser crashed while scraping")

                self.cursor.execute(
                    f"DELETE FROM places_info WHERE places_idplace = {place['idplace']}")
                self.mydb.commit()

                print(self.data)

                if self.data['nombre_en'] is None or self.data['nombre_es'] is None:
                    continue

                self.cursor.execute(
                    """
                        INSERT INTO places_info (
                            places_idplace,
                            nombre_es,
                            nombre_en,
                            descripcion_short_es,
                            descripcion_short_en,
                            descripcion_long_es,
                            descripcion_long_en,
                            direccion,
                            web,
                            telefono,
                            email,
                            lat,
                            lng,
                            imagenes,
                            duracion,
                            rating,
                            costos,
                            horarios,
                            reviews_en,
                            reviews_es,
                            categorias
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        self.data['idplace'],
                        self.data['nombre_es'],
                        self.data['nombre_en'],
                        self.data['descripcion_short_es'],
                        self.data['descripcion_short_en'],
                        self.data['descripcion_long_es'],
                        self.data['descripcion_long_en'],
                        self.data['direccion'],
                        self.data['web'],
                        self.data['telefono'],
                        self.data['email'],
                        self.data['lat'],
                        self.data['lng'],
                        json.dumps(self.data['imagenes']),
                        self.data['duracion'],
                        self.data['rating'],
                        json.dumps(self.data['costos']),
                        json.dumps(self.data['horarios']),
                        json.dumps(self.data['reviews_en']),
                        json.dumps(self.data['reviews_es']),
                        json.dumps(self.data['categorias'])
                    ))
                self.mydb.commit()

                print(
                    f"{place['nombre_place']} -> info inserted")

            self.done = True
            if self.driver is not None:
                self.driver.close()

        def run(self):
            while not self.done:
                try:
                    self.scrape()
                except Exception as e:
                    print('Exception:', e)
                    traceback.print_exc()
                    if self.driver is not None:
                        try:
                            self.driver.close()
                        except:
                            pass
                            # print('Exception:', e)
                            # traceback.print_exc()

    task = MapsScrapingThread()
    task.run()


threads = []

if __name__ == "__main__":
    print('Starting threads')
    for i in range(thread_count):
        threads.append(Process(target=init))
        threads[i].start()

    while True:
        pass
