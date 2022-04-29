import json
import time
import os
import random
import sys
import traceback
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
from maps_scraper import MapsScraper
import mysql.connector

load_dotenv()

thread_count = 1

if (len(sys.argv) > 1):
    try:
        thread_count = int(sys.argv[1])
    except:
        print('Invalid number for thread count')
        sys.exit(1)

threads = []


# calculate elapsed time
def elapsed_time(start_time):
    return time.time() - start_time


def init():
    class element_has_loaded_suggestions(object):
        def __call__(self, driver):
            return len(driver.find_elements(By.CSS_SELECTOR, '.XOeJFd.rHFvzd ul')) > 0 or len(driver.find_elements(By.CSS_SELECTOR, '.XOeJFd.rHFvzd .rZ2Tg')) > 0

    class ScrapingThread():

        def __init__(self):
            self.url = 'https://www.google.com/travel/things-to-do?hl=es-419&dest_mid=%2Fm%2F01qgv7'
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
            self.ciudades = []
            self.json_data = {}

        def get_url(self, lang):
            return self.url.replace('es-419', 'en' if lang == 'en' else 'es-419')

        def init_driver(self,):
            if self.driver is not None:
                try:
                    self.driver.close()
                except:
                    pass
            options = webdriver.ChromeOptions()
            # options.add_argument('window-position=2560,0')
            # options.add_argument('window-position=960,0')
            # options.add_experimental_option(
            #     'prefs', {'intl.accept_languages': 'en-GB' if language == 'en' else 'es-ES'})

            self.driver = webdriver.Chrome(
                chrome_options=options)

        def get_place_id(self, nombre_place):
            try:
                for request in self.driver.requests:
                    if request.response and 'batchexecute' in request.url:
                        body = decode(request.response.body, request.response.headers.get(
                            'Content-Encoding', 'identity'))
                        body = body.decode('utf-8').replace('\\/', '/') \
                            .replace("\\xa0", " ") \
                            .replace("\\u003d", "=") \
                            .replace('\\\\\\"', '') \
                            .replace('\\"', '"') \
                            .replace('\\', '') \

                        if nombre_place in body and 'placeid=' in body:
                            return body.split('placeid=')[1].split('"')[0]

                raise Exception('place id not found')

            except Exception as e:
                # print(e)
                # traceback.print_exc()
                return None

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

        def get_ciudades(self):
            self.cursor.execute("""
                SELECT p.nombre_pais, d.nombre_departamento, c.nombre_ciudad, c.idciudad, null as dest_mid FROM ciudades c 
                JOIN departamentos d ON d.iddepartamento = c.departamentos_iddepartamento
                JOIN paises p ON p.idpais = d.paises_idpais
                WHERE c.idciudad NOT IN (SELECT idciudad FROM cache) AND p.nombre_pais = 'Chile'
            """)
            ciudades = self.cursor.fetchall()

            random.shuffle(ciudades)

            return ciudades

        def check_if_cached(self, idciudad):
            self.cursor.execute(
                f"SELECT * FROM cache WHERE idciudad = {idciudad}")
            exists = self.cursor.fetchall()
            return len(exists) > 0

        def add_cached(self, idciudad):
            self.cursor.execute(
                f"INSERT INTO cache(idciudad) VALUES ({idciudad})")
            self.mydb.commit()

        def search_place(self, ciudad, lang):
            if ciudad['dest_mid'] is None:
                url = self.get_url(lang)
                self.driver.get(url)
                input_ciudad = self.driver.find_element(By.CSS_SELECTOR,
                                                        'input[jsname="yrriRe"]')

                action = ActionChains(self.driver)

                action.double_click(input_ciudad)
                for letter in ciudad['nombre_ciudad']:
                    action.send_keys(letter)
                action.perform()

                WebDriverWait(self.driver, 10).until(
                    element_has_loaded_suggestions())

                suggestions = self.driver.find_elements(
                    By.CSS_SELECTOR, 'ul.DFGgtd li')

                match = None

                if len(suggestions) == 0:
                    return False

                for suggestion in suggestions:
                    if ciudad['nombre_departamento'].lower().strip() in suggestion.text.lower().strip():
                        match = suggestion
                        break

                    if ciudad['nombre_pais'].lower().strip() in suggestion.text.lower().strip():
                        match = suggestion
                        break

                if match is None:
                    return False

                match.click()

                self.driver.execute_script("""
                    var element = document.querySelector(".kQb6Eb");
                    if (element)
                        element.parentNode.removeChild(element);
                """)

            else:
                self.driver.get(
                    f"https://www.google.com/travel/things-to-do?hl={'en' if lang == 'en' else 'es-419'}&dest_mid={ciudad['dest_mid']}")

            try:
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '.kQb6Eb')))
            except:
                return False

            if ciudad['dest_mid'] is None:
                ciudad['dest_mid'] = self.driver.current_url.split('dest_mid=')[
                    1].split('&')[0]

            self.driver.execute_script("""
                var element = document.querySelector(".kQb6Eb");
                if (element)
                    element.parentNode.removeChild(element);
            """)

            self.driver.find_element(
                By.CSS_SELECTOR, 'button[class="VfPpkd-LgbsSe VfPpkd-LgbsSe-OWXEXe-INsAgc VfPpkd-LgbsSe-OWXEXe-Bz112c-M1Soyc VfPpkd-LgbsSe-OWXEXe-dgl2Hf Rj2Mlf OLiIxf PDpWxe qfvgSe J3Eqid"]').click()

            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '.kQb6Eb')))

            return True

        def get_nombre_place(self, place_element):
            try:
                return place_element.find_element(By.CSS_SELECTOR, '.skFvHc.YmWhbc').text

            except:
                print('Nombre not found')
                return None

        def get_descripcion_ttt(self, place_element):
            try:
                return place_element.find_element(By.CSS_SELECTOR, '.nFoFM').text

            except:
                print('Descripcion Things To Do not found')
                return None

        def get_rating(self, place_element):
            try:
                return place_element.find_element(By.CSS_SELECTOR, '.KFi5wf.lA0BZ').text

            except:
                print('Rating not found')
                return None

        def get_imagenes(self):
            try:
                imagenes_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, '.U4rdx c-wiz .NBZP0e.xbmkib .QtzoWd img')

                imagenes = []
                for imagen_element in imagenes_elements:
                    ActionChains(self.driver).move_to_element(
                        imagen_element).perform()

                    url = imagen_element.get_attribute('src')

                    if url is None or 'google.com/maps' in url:
                        continue

                    imagen_url = url.replace(
                        'lh5', 'lh3').split('=')[0] + '=s0'

                    imagenes.append(imagen_url)

                return imagenes

            except:
                print('Imagenes not found')
                return None

        def scrape(self):
            global cached, cached_mutex

            self.ciudades = self.get_ciudades()
            self.done = False
            self.init_driver()

            for ciudad in self.ciudades:
                print(
                    f"{ciudad['nombre_pais']} - {ciudad['nombre_departamento']} - {ciudad['nombre_ciudad']}")

                start_time = time.time()

                if (self.check_if_cached(ciudad['idciudad'])):
                    print('City already cached')
                    continue

                places = []
                Found = True

                for lang in ['es', 'en']:
                    if not Found:
                        continue

                    if not self.search_place(ciudad, lang):
                        Found = False
                        continue

                    place_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, '.kQb6Eb .f4hh3d')

                    init_data = {
                        'data_card_id': None,
                        'nombre_place_es': None,
                        'nombre_place_en': None,
                        'descripcion_ttt_es': None,
                        'descripcion_ttt_en': None,
                        'rating': None,
                        'place_id': None,
                        'descripcion_short_en': None,
                        'descripcion_short_es': None,
                        'descripcion_long_en': None,
                        'descripcion_long_es': None,
                        'direccion_es': None,
                        'direccion_en': None,
                        'web': None,
                        'telefono': None,
                        'email': None,
                        'lat': None,
                        'lng': None,
                        'imagenes': [],
                        'duracion': None,
                        'rating': None,
                        'costos': [],
                        'horarios': [],
                        'reviews_en': [],
                        'reviews_es': [],
                        'categorias': []
                    }

                    place = init_data.copy()

                    for place_element in place_elements:
                        place = init_data.copy()

                        self.driver.execute_script("""
                            var element = document.querySelector(".U4rdx");
                            if (element)
                                element.parentNode.removeChild(element);
                        """)

                        ActionChains(self.driver).move_to_element(
                            place_element).perform()

                        place_element.click()

                        WebDriverWait(self.driver, 60).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, '.U4rdx c-wiz')))

                        idx = None
                        for i in range(len(places)):
                            if places[i]['data_card_id'] == place_element.get_attribute('data-card-id'):
                                idx = i
                                place = places[i]
                                break

                        if place['data_card_id'] is None:
                            place['data_card_id'] = place_element.get_attribute(
                                'data-card-id')

                        if place[f'nombre_place_{lang}'] is None:
                            place[f'nombre_place_{lang}'] = self.get_nombre_place(
                                place_element)

                        if place[f'descripcion_ttt_{lang}'] is None:
                            place[f'descripcion_ttt_{lang}'] = self.get_descripcion_ttt(
                                place_element)

                        if place[f'rating'] is None:
                            place[f'rating'] = self.get_rating(
                                place_element)

                        if place[f'imagenes'] == []:
                            place[f'imagenes'] = self.get_imagenes()

                        if place[f'place_id'] is None:
                            place[f'place_id'] = self.get_place_id(
                                place[f'nombre_place_{lang}'])

                        maps_data = MapsScraper().scrape(self.driver, place, lang)

                        if maps_data is not None:
                            for place_key in place.keys():
                                if place[place_key] is None or place[place_key] == []:
                                    if place_key in maps_data and (maps_data[place_key] is not None or maps_data[place_key] != []):
                                        place[place_key] = maps_data[place_key]

                        if idx is None:
                            places.append(place)
                        else:
                            places[idx] = place

                self.cursor.execute(
                    f"DELETE FROM places where ciudades_idciudad = {ciudad['idciudad']}")
                self.mydb.commit()

                values = []
                for place in places:
                    print(place)
                    values.append((
                        ciudad['idciudad'],
                        place['data_card_id'],
                        place['place_id'],
                        place['nombre_place_es'],
                        place['nombre_place_en'],
                        place['descripcion_ttt_es'],
                        place['descripcion_ttt_en'],
                        place['descripcion_short_es'],
                        place['descripcion_short_en'],
                        place['descripcion_long_es'],
                        place['descripcion_long_en'],
                        place['direccion_es'],
                        place['direccion_en'],
                        place['web'],
                        place['telefono'],
                        place['email'],
                        place['lat'],
                        place['lng'],
                        json.dumps(place['imagenes']),
                        place['duracion'],
                        place['rating'],
                        json.dumps(place['costos']),
                        json.dumps(place['horarios']),
                        json.dumps(place['reviews_es']),
                        json.dumps(place['reviews_en']),
                        json.dumps(place['categorias']),
                        True,
                    ))

                self.cursor.executemany("""
                    INSERT INTO places(
                        ciudades_idciudad, 
                        data_card_id,
                        place_id,
                        nombre_place_es,
                        nombre_place_en,
                        descripcion_ttt_es,
                        descripcion_ttt_en,
                        descripcion_short_es,
                        descripcion_short_en,
                        descripcion_long_es,
                        descripcion_long_en,
                        direccion_es,
                        direccion_en,
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
                        reviews_es,
                        reviews_en,
                        categorias,
                        maps_scraped
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, values)
                self.mydb.commit()
                print(
                    f"{ciudad['nombre_ciudad']} -> {self.cursor.rowcount} places inserted")

                print(f"elapsed time: {time.time() - start_time} seconds")

                self.add_cached(ciudad['idciudad'])

            self.done = True
            self.driver.close()

        def run(self):
            while not self.done:
                try:
                    self.scrape()
                except Exception as e:
                    print(e)
                    traceback.print_exc()
                    if self.driver is not None:
                        try:
                            self.driver.close()
                        except:
                            print(e)

    task = ScrapingThread()
    task.run()


if __name__ == "__main__":
    print('Starting threads')
    for i in range(thread_count):
        threads.append(Process(target=init))
        threads[i].start()

    while True:
        pass
