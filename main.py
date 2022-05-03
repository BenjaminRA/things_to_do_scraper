import json
import time
import os
import random
import sys
import argparse
import traceback
from multiprocessing import Process
from typing import final
from dotenv import load_dotenv
from pymongo import InsertOne, UpdateOne
from seleniumwire import webdriver
from seleniumwire.utils import decode
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from maps_scraper import MapsScraper
from db.mongodb import get_client
from decimal import Decimal

parser = argparse.ArgumentParser()

parser.add_argument('--threads', type=int, default=1,
                    help='Number of threads to run (default: 1)')
parser.add_argument('--country', type=str, default='',
                    help='Country to scrape (default: it will scrape all countries)')
parser.add_argument('--priority', type=str, default='',
                    help='Scrape countries with specified priority (default: it will scrape all countries)')
parser.add_argument('--chunck', type=int, default=100,
                    help='Chunck size fetch from all three collections on the db. (default: 100 => 100 * 3 = 300)')

args = parser.parse_args()

thread_count = args.threads

threads = []

PAIS_TERRITORY = 1
DEPARTAMENTO_TERRITORY = 2
CIUDAD_TERRITORY = 3

load_dotenv()

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
            self.client = get_client()
            self.ciudades = []
            self.json_data = {}

        def get_url(self, lang):
            """
            The things to do url to scrape for the given language.
            """
            return self.url.replace('es-419', 'en' if lang == 'en' else 'es-419')

        def init_driver(self):
            """
            Initializes the chrome driver.
            """
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

        def get_territory_type(self, territory):
            """
            Returns the territory type:
            CIUDAD_TERRITORY, DEPARTAMENTO_TERRITORY or PAIS_TERRITORY
            """
            if 'ciudad_id' in territory:
                return CIUDAD_TERRITORY

            elif 'departamento_id' in territory and 'ciudad_id' not in territory:
                return DEPARTAMENTO_TERRITORY

            else:
                return PAIS_TERRITORY

        def get_territory_name(self, territory):
            """
            Returns the territory name, given the territory type.
            """
            if territory['type'] == CIUDAD_TERRITORY:
                return f"{territory['ciudad_nombre']} ({territory['departamento_nombre']}) ({territory['pais_nombre']})"

            elif territory['type'] == DEPARTAMENTO_TERRITORY:
                return f"{territory['departamento_nombre']} ({territory['pais_nombre']})"

            else:
                return territory['pais_nombre']

        def get_place_id(self, nombre_place):
            """
            Returns the place id given the place name.
            It looks through the network requests to find where google fetches the place info,
            then it parses the response to get the place id.
            """
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

        # def get_json(self):
        #     self.json_data = {}
        #     try:
        #         for request in self.driver.requests:
        #             if request.response and 'google.com/search?' in request.url:
        #                 body = decode(request.response.body, request.response.headers.get(
        #                     'Content-Encoding', 'identity'))
        #                 body = (body.decode('utf-8').split("\")]}'\\n")
        #                         [1].split(']","e')[0] + ']') \
        #                     .replace('\\/', '/') \
        #                     .replace('\\\\\\"', '') \
        #                     .replace('\\"', '"') \
        #                     .replace('\\', '') \
        #                     .replace("\\xa0", " ") \

        #                 self.json_data = json.loads(body)[0][1][0][14]

        #             if request.response and 'google.com/maps/preview/place' in request.url:
        #                 body = decode(request.response.body, request.response.headers.get(
        #                     'Content-Encoding', 'identity'))

        #                 body = body.decode('utf-8')[5:]

        #                 self.json_data = json.loads(body)[6]

        #     except Exception as e:
        #         print(e)
        #         traceback.print_exc()

        def get_places_to_scrape(self):
            """
            Returns the places to scrape from the mongoDB database,
            given the language and the priority provided by the user in the command line.
            """
            query = {'scraped': False}

            if args.country != '':
                query['pais_nombre'] = args.country

            if args.priority != '':
                query['priority'] = int(args.priority)

            ciudades = list(self.client.ciudades.find(
                query).sort('priority', 1).limit(args.chunck))
            departamentos = list(self.client.departamentos.find(
                query).sort('priority', 1).limit(args.chunck))
            paises = list(self.client.paises.find(
                query).sort('priority', 1).limit(args.chunck))

            random.shuffle(ciudades)
            random.shuffle(departamentos)
            random.shuffle(paises)

            return ciudades + departamentos + paises

        def check_territory_scraped(self, territory):
            """
            Returns True if the territory has been scraped, False otherwise.
            """
            if territory['type'] == CIUDAD_TERRITORY:
                return self.client.ciudades.find_one({'ciudad_id': territory['ciudad_id']})['scraped']

            elif territory['type'] == DEPARTAMENTO_TERRITORY:
                return self.client.departamentos.find_one({'departamento_id': territory['departamento_id']})['scraped']

            else:
                return self.client.paises.find_one({'pais_id': territory['pais_id']})['scraped']

        def check_attraction_scraped(self, attraction_id):
            """
            Returns True if the attraction has been scraped, False otherwise.
            """
            return self.client.atracciones.find_one({'atraccion_id': attraction_id})

        def set_scraped(self, territory):
            """
            Sets the place as scraped in the mongoDB database.
            """
            if territory['type'] == CIUDAD_TERRITORY:
                self.client.ciudades.update_one(
                    {'ciudad_id': territory['ciudad_id']}, {'$set': {'scraped': True}})
            elif territory['type'] == DEPARTAMENTO_TERRITORY:
                self.client.departamentos.update_one(
                    {'departamento_id': territory['departamento_id']}, {'$set': {'scraped': True}})
            else:
                self.client.paises.update_one(
                    {'pais_id': territory['pais_id']}, {'$set': {'scraped': True}})

        def search_place(self, territory, lang):
            """
            Searches for the place in google's things to do.
            It types the place name on the input field, and then checks wheter the place shows up in the suggestion box.
            If it does, it clicks on the place and waits for the data to load.
            """
            if 'dest_mid' not in territory or territory['dest_mid'] == None:
                url = self.get_url(lang)
                self.driver.get(url)

                input_ciudad = self.driver.find_element(By.CSS_SELECTOR,
                                                        'input[jsname="yrriRe"]')

                action = ActionChains(self.driver)

                action.double_click(input_ciudad)

                query = ''

                if territory['type'] == CIUDAD_TERRITORY:
                    query = territory['ciudad_nombre']
                elif territory['type'] == DEPARTAMENTO_TERRITORY:
                    query = territory['departamento_nombre']
                else:
                    query = territory['pais_nombre']

                for letter in query:
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
                    if territory['type'] == PAIS_TERRITORY:
                        if 'país' in suggestion.text.lower().strip():
                            match = suggestion
                            break

                        if 'isla' in suggestion.text.lower().strip():
                            match = suggestion
                            break

                        if 'imperio' in suggestion.text.lower().strip():
                            match = suggestion
                            break

                        if 'república' in suggestion.text.lower().strip():
                            match = suggestion
                            break
                    else:
                        if 'departamento_nombre' in territory:
                            if territory['departamento_nombre'].lower().strip() in suggestion.text.lower().strip():
                                match = suggestion
                                break

                        if 'pais_nombre' in territory:
                            if territory['pais_nombre'].lower().strip() in suggestion.text.lower().strip():
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
                    f"https://www.google.com/travel/things-to-do?hl={'en' if lang == 'en' else 'es-419'}&dest_mid={territory['dest_mid']}")

            try:
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '.kQb6Eb')))
            except:
                return False

            if 'dest_mid' not in territory or territory['dest_mid'] is None:
                territory['dest_mid'] = self.driver.current_url.split('dest_mid=')[
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
            """
            Retrieves the name of the place from the place_element, where place_element is the element containing the place's info.
            """
            try:
                return place_element.find_element(By.CSS_SELECTOR, '.skFvHc.YmWhbc').text

            except:
                print('Nombre not found')
                return None

        def get_descripcion_ttt(self, place_element):
            """
            Retrieves the description of the place from the place_element, where place_element is the element containing the place's info.
            """
            try:
                return place_element.find_element(By.CSS_SELECTOR, '.nFoFM').text

            except:
                print('Descripcion Things To Do not found')
                return None

        def get_rating(self, place_element):
            """
            Retrieves the rating of the place from the place_element, where place_element is the element containing the place's info.
            """
            try:
                return place_element.find_element(By.CSS_SELECTOR, '.KFi5wf.lA0BZ').text

            except:
                print('Rating not found')
                return None

        def get_imagenes(self):
            """
            Retrieves the images of the place, provided that the place has images and the box of the place's info has been clicked.
            It loops trough the images, changes the url to get the original image, and returns the list of images.
            """
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

                    if 'encrypted-' in url:
                        imagenes.append(url)
                        continue

                    imagen_url = url.replace(
                        'lh5', 'lh3').split('=')[0] + '=s0'

                    imagenes.append(imagen_url)

                return imagenes

            except:
                print('Imagenes not found')
                return None

        def scrape_territory(self, territory):
            """
            Scrape the territory, provided that the territory has not been scraped yet.
            """
            territory_type = self.get_territory_type(territory)
            territory['type'] = territory_type

            if self.check_territory_scraped(territory):
                print(
                    f"{self.get_territory_name(territory)} already scraped")
                return False

            places = []
            Found = True

            for lang in ['es', 'en']:
                if not Found:
                    continue

                if not self.search_place(territory, lang):
                    Found = False
                    continue

                place_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, '.kQb6Eb .f4hh3d')

                init_data = {
                    '_id': None,
                    'data_card_id': None,
                    'nombre_place_es': None,
                    'nombre_place_en': None,
                    'descripcion_ttt_es': None,
                    'descripcion_ttt_en': None,
                    'rating': None,
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
                    'categorias': [],
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

                    try:
                        WebDriverWait(self.driver, 30).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, '.U4rdx c-wiz')))
                    except:
                        place_element.click()
                        WebDriverWait(self.driver, 120).until(
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

                    if place[f'_id'] is None:
                        place[f'_id'] = self.get_place_id(
                            place[f'nombre_place_{lang}'])

                    maps_data = MapsScraper().scrape(self.driver, place, lang)

                    if maps_data is not None:
                        for place_key in place.keys():
                            if place[place_key] is None or place[place_key] == []:
                                if place_key in maps_data and (maps_data[place_key] is not None or maps_data[place_key] != []):
                                    place[place_key] = maps_data[place_key]

                    # If doesn't have google's place id, it means that the place does not have useful info
                    if place[f'_id'] is None:
                        continue

                    if territory['type'] == CIUDAD_TERRITORY:
                        place['ciudad'] = territory['ciudad_id']
                        self.client.atracciones.delete_many(
                            {'ciudad_id': territory['ciudad_id']})

                    elif territory['type'] == DEPARTAMENTO_TERRITORY:
                        place['departamento_id'] = territory['departamento_id']
                        self.client.atracciones.delete_many(
                            {'departamento_id': territory['departamento_id']})

                    else:
                        place['pais_id'] = territory['pais_id']
                        self.client.atracciones.delete_many(
                            {'pais_id': territory['pais_id']})

                    if idx is None:
                        places.append(place)
                    else:
                        places[idx] = place

            values = []
            for place in places:

                attraction = self.check_attraction_scraped(place['_id'])
                if attraction is not None:
                    set_query = {}
                    if attraction['ciudad_id'] is None and place['ciudad_id'] is not None:
                        set_query['ciudad_id'] = place['ciudad_id']

                    if attraction['departamento_id'] is None and place['departamento_id'] is not None:
                        set_query['departamento_id'] = place['departamento_id']

                    if attraction['pais_id'] is None and place['pais_id'] is not None:
                        set_query['pais_id'] = place['pais_id']

                    print(
                        f"{place['_id']} {place['nombre_place_es']} already scraped")

                    values.append(UpdateOne({
                        '_id': place['_id']
                    }, {
                        '$set': set_query
                    }))
                    continue

                values.append(InsertOne(place))

            if len(values) > 0:
                self.client.atracciones.bulk_write(values)

            print(
                f"{self.get_territory_name(territory)} -> {len(values)} attractions inserted")

            self.set_scraped(territory)

        def scrape(self):
            self.territories = self.get_places_to_scrape()
            self.done = len(self.territories) == 0

            for territory in self.territories:
                self.init_driver()
                self.scrape_territory(territory)
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
