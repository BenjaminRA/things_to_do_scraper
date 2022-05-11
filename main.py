import json
import time
import os
import random
import sys
import argparse
import traceback
from datetime import datetime
from multiprocessing import Process
from typing import final
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import InsertOne, UpdateOne
from seleniumwire import webdriver
from seleniumwire.utils import decode
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.window import WindowTypes
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
parser.add_argument('--state', type=str, default='',
                    help='State to scrape (default: it will scrape all states)')
parser.add_argument('--city', type=str, default='',
                    help='City to scrape (default: it will scrape all cities)')
parser.add_argument('--priority', type=str, default='',
                    help='Scrape places with specified priority (default: it will scrape all places)')
parser.add_argument('--priority_lte', type=str, default='',
                    help='Scrape places with greater priority (default: it will scrape all places)')
parser.add_argument('--group', type=str, default='',
                    help='Scrape places from specific group (default: it will scrape all places)')
parser.add_argument('--chunck', type=int, default=1500,
                    help='Chunck size fetch from all three collections on the db. (default: 1500)')
parser.add_argument('--offset', type=int, default=0,
                    help='Windows X position offset. (default: 0)')
parser.add_argument('--verbose', type=bool, default=False,
                    help='Verbose mode (default: False)')

args = parser.parse_args()

thread_count = args.threads

threads = []

COUNTRY_TERRITORY = 1
STATE_TERRITORY = 2
CITY_TERRITORY = 3

load_dotenv()

# calculate elapsed time


def elapsed_time(start_time):
    return time.time() - start_time


def init(idx):
    class element_has_loaded_suggestions(object):
        def __call__(self, driver):
            return len(driver.find_elements(By.CSS_SELECTOR, '.XOeJFd.rHFvzd ul')) > 0 or len(driver.find_elements(By.CSS_SELECTOR, '.XOeJFd.rHFvzd .rZ2Tg')) > 0

    class ScrapingThread():

        def __init__(self, idx):
            self.url = 'https://www.google.com/travel/things-to-do?hl=es-419&dest_mid=%2Fm%2F01qgv7'
            self.driver = None
            self.done = False
            self.daemon = True
            self.client = get_client()
            self.idx = idx
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
            print('Scraper Version: 1.7.5')
            if self.driver is not None:
                try:
                    self.driver.close()
                except:
                    pass
            options = webdriver.ChromeOptions()
            options.add_argument(
                f"window-position={args.offset + (self.idx)*400},0")
            # options.add_argument('window-position=960,0')
            # options.add_experimental_option(
            #     'prefs', {'intl.accept_languages': 'en-GB' if language == 'en' else 'es-ES'})

            self.driver = webdriver.Chrome(
                chrome_options=options)

        def get_territory_type(self, territory):
            """
            Returns the territory type:
            CITY_TERRITORY, STATE_TERRITORY or COUNTRY_TERRITORY
            """
            if territory['city'] is not None:
                return CITY_TERRITORY

            elif territory['state'] is not None and territory['city'] is None:
                return STATE_TERRITORY

            else:
                return COUNTRY_TERRITORY

        def get_territory_name(self, territory):
            """
            Returns the territory name, given the territory type.
            """
            if territory['type'] == CITY_TERRITORY:
                return f"{territory['city']} ({territory['state']}) ({territory['country']})"

            elif territory['type'] == STATE_TERRITORY:
                return f"{territory['state']} ({territory['country']})"

            else:
                return territory['country']

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
                if args.verbose:
                    print(f'Error getting place id: {e}')
                    print(e)
                    traceback.print_exc()
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
                query['country'] = args.country

            if args.state != '':
                query['state'] = args.state

            if args.city != '':
                query['city'] = args.city

            if args.priority != '':
                query['priority'] = int(args.priority)

            if args.priority_lte != '':
                query['priority'] = {'$lte': int(args.priority_lte)}

            if args.group != '':
                query['group'] = args.group

            ciudades = list(self.client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].find(
                query).sort('priority', 1).limit(args.chunck))

            random.shuffle(ciudades)

            return ciudades

        def check_territory_scraped(self, territory):
            """
            Returns True if the territory has been scraped, False otherwise.
            """
            aux = self.client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].find_one({'_id': territory['_id']})
            return 'scraped' in aux and aux['scraped']

        def fetch_attraction(self, attraction_id):
            """
            Returns the attraction by googlePlaceId.
            """
            return self.client[os.getenv(
                'MONGODB_DBNAME_PLACES_COLLECTION_NAME')].find_one({'googlePlaceId': attraction_id})

        def set_scraped(self, territory):
            """
            Sets the place as scraped in the mongoDB database.
            """
            self.client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].update_one({'_id': territory['_id']}, {
                    '$set': {'scraped': True}})

            print(f"{self.get_territory_name(territory)} scraped")

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

                input_ciudad.clear()
                input_ciudad.send_keys(Keys.CONTROL + "a")
                input_ciudad.send_keys(Keys.DELETE)

                action = ActionChains(self.driver)

                action.double_click(input_ciudad)

                query = ''

                if territory['type'] == CITY_TERRITORY:
                    query = territory['city'] if lang == 'es' else territory['cityEn']
                elif territory['type'] == STATE_TERRITORY:
                    query = territory['state'] if lang == 'es' else territory['stateEn']
                else:
                    query = territory['country'] if lang == 'es' else territory['countryEn']

                for letter in query:
                    action.send_keys(letter)
                action.perform()

                WebDriverWait(self.driver, 20).until(
                    element_has_loaded_suggestions())

                suggestions = self.driver.find_elements(
                    By.CSS_SELECTOR, 'ul.DFGgtd li')

                match = None

                if len(suggestions) == 0:
                    return False

                for suggestion in suggestions:
                    if territory['type'] == COUNTRY_TERRITORY:
                        if ('país' if lang == 'es' else 'country') in suggestion.text.lower().strip():
                            match = suggestion
                            break

                        if ('isla' if lang == 'es' else 'island') in suggestion.text.lower().strip():
                            match = suggestion
                            break

                        if ('imperio' if lang == 'es' else 'empire') in suggestion.text.lower().strip():
                            match = suggestion
                            break

                        if ('república' if lang == 'es' else 'republic') in suggestion.text.lower().strip():
                            match = suggestion
                            break
                    else:
                        if territory['state'] is not None:
                            if territory['state'].lower().strip() in suggestion.text.lower().strip():
                                match = suggestion
                                break

                        if territory['country'] is not None:
                            if territory['country'].lower().strip() in suggestion.text.lower().strip():
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
                WebDriverWait(self.driver, 15).until(EC.presence_of_element_located(
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
                if args.verbose:
                    print('Nombre not found')
                return None

        def get_descripcion_ttt(self, place_element):
            """
            Retrieves the description of the place from the place_element, where place_element is the element containing the place's info.
            """
            try:
                return place_element.find_element(By.CSS_SELECTOR, '.nFoFM').text

            except:
                if args.verbose:
                    print('Descripcion Things To Do not found')
                return None

        def get_stars(self, place_element):
            """
            Retrieves the stars of the place from the place_element, where place_element is the element containing the place's info.
            """
            try:
                return place_element.find_element(By.CSS_SELECTOR, '.KFi5wf.lA0BZ').text

            except:
                if args.verbose:
                    print('stars not found')
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
                if args.verbose:
                    print('Imagenes not found')
                return None

        def scrape_by_language_new_tab(self, territory, place, lang):
            if place['data_card_id'] is None:
                return False

            main_windows_name = self.driver.window_handles[0]
            self.driver.switch_to.new_window(WindowTypes.TAB)

            self.driver.set_page_load_timeout(60)

            if not self.search_place(territory, lang):
                return False

            self.driver.execute_script("""
                var element = document.querySelector(".U4rdx");
                if (element)
                    element.parentNode.removeChild(element);
            """)

            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"div[data-card-id=\"{place['data_card_id']}\"]")))

            place_element = self.driver.find_element(
                By.CSS_SELECTOR, f"div[data-card-id=\"{place['data_card_id']}\"]")

            ActionChains(self.driver).move_to_element(
                place_element).perform()

            place_element.click()

            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.U4rdx c-wiz')))

            if place[f'nombre_place_{lang}'] is None:
                place[f'nombre_place_{lang}'] = self.get_nombre_place(
                    place_element)

            if place[f'descripcion_ttt_{lang}'] is None:
                place[f'descripcion_ttt_{lang}'] = self.get_descripcion_ttt(
                    place_element)

            maps_data = MapsScraper(args.verbose).scrape(
                self.driver, place, lang, 1)

            if maps_data is not None:
                for place_key in place.keys():
                    if place[place_key] is None or place[place_key] == [] or place[place_key] == {}:
                        if place_key in maps_data and (maps_data[place_key] is not None or maps_data[place_key] != [] or maps_data[place_key] != {}):
                            place[place_key] = maps_data[place_key]

            if self.driver is not None:
                try:
                    self.driver.backend.storage.clear_requests()
                except:
                    pass
                self.driver.close()
                self.driver.switch_to.window(
                    window_name=main_windows_name)

        def get_classes(self):
            """
            Returns the classes of the place.
            """
            return 'color-' + str(random.randint(1, 9))

        def get_tags(self, place, territory):
            """
            Returns the tags of the place.
            """

            tags = []
            if territory['city'] is not None:
                tags.append(territory['city'].lower().strip())

            if territory['state'] is not None:
                tags.append(territory['state'].lower().strip())

            if territory['country'] is not None:
                tags.append(territory['country'].lower().strip())

            if territory['cityEn'] is not None:
                tags.append(territory['cityEn'].lower().strip())

            if territory['stateEn'] is not None:
                tags.append(territory['stateEn'].lower().strip())

            if territory['countryEn'] is not None:
                tags.append(territory['countryEn'].lower().strip())

            return place['categorias'] + tags

        def delete_repeated_attractions(self, place):
            """
            Deletes the repeated attractions from the place.
            """
            repeated_attractions = list(self.client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].find({
                'googlePlaceId': place['googlePlaceId']}))

            if len(repeated_attractions) > 1:
                max_locations = 0
                max_id = None
                for repeated_attraction in repeated_attractions:
                    if len(repeated_attraction['location']) > max_locations:
                        max_locations = len(repeated_attraction['location'])
                        max_id = repeated_attraction['_id']

                if max_id is not None:
                    for repeated_attraction in repeated_attractions:
                        if repeated_attraction['_id'] != max_id:
                            self.client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].delete_one(
                                {'_id': repeated_attraction['_id']})

        def check_attraction_repeated(self, place, territory, lang):
            """
            Checks if the attraction has been inserted.
            """
            attraction = self.fetch_attraction(place['googlePlaceId'])

            if attraction is not None:
                self.delete_repeated_attractions(place)

                set_query = {}
                temp = attraction['location']
                if territory['_id'] not in temp:
                    temp.append(territory['_id'])

                set_query['location'] = temp

                print(
                    f"{place['googlePlaceId']} \"{place[f'nombre_place_{lang}']}\" already scraped")

                self.client[os.getenv(
                    'MONGODB_DBNAME_PLACES_COLLECTION_NAME')].update_one({
                        '_id': attraction['_id']
                    }, {
                        '$set': set_query
                    })

                return True

            return False

        def scrape_territory(self, territory, lang='en'):
            """
            Scrape the territory, provided that the territory has not been scraped yet.
            """
            territory_type = self.get_territory_type(territory)
            territory['type'] = territory_type

            if self.check_territory_scraped(territory):
                print(
                    f"{self.get_territory_name(territory)} already scraped")
                return False

            if not self.search_place(territory, lang):
                return True

            place_elements = self.driver.find_elements(
                By.CSS_SELECTOR, '.kQb6Eb .f4hh3d')

            init_data = {
                'googlePlaceId': None,
                'data_card_id': None,
                'nombre_place_es': None,
                'nombre_place_en': None,
                'place': None,
                'placeEn': None,
                'stars': None,
                'descripcion_ttt_es': None,
                'descripcion_ttt_en': None,
                'descripcion_short_en': None,
                'descripcion_short_es': None,
                'descripcion_long_en': None,
                'descripcion_long_es': None,
                'direccion_en': None,
                'direccion_es': None,
                'title': None,
                'titleEn': None,
                'descriptionLarge': None,
                'descriptionEn': None,
                'web': None,
                'telf': None,
                'mail': None,
                'lat': None,
                'lon': None,
                'imagenes': [],
                'location': [],
                'duration': None,
                'costos': [],
                'workingH': {},
                'reviews_en': [],
                'reviews_es': [],
                'categorias': []
            }

            for place_element in place_elements:
                place = init_data.copy()
                start_time = time.time()

                self.driver.execute_script("""
                    var element = document.querySelector(".U4rdx");
                    if (element)
                        element.parentNode.removeChild(element);
                """)

                ActionChains(self.driver).move_to_element(
                    place_element).perform()

                try:
                    self.driver.backend.storage.clear_requests()
                except:
                    pass

                place_element.click()

                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.U4rdx c-wiz')))

                if place['data_card_id'] is None:
                    place['data_card_id'] = place_element.get_attribute(
                        'data-card-id')

                if place[f'nombre_place_{lang}'] is None:
                    place[f'nombre_place_{lang}'] = self.get_nombre_place(
                        place_element)

                if place[f'googlePlaceId'] is None:
                    place[f'googlePlaceId'] = self.get_place_id(
                        place[f'nombre_place_{lang}'])

                # If doesn't have google's place id, it means that the place does not have useful information
                if place[f'googlePlaceId'] is None:
                    continue

                if self.check_attraction_repeated(place, territory, lang):
                    continue

                if place[f'descripcion_ttt_{lang}'] is None:
                    place[f'descripcion_ttt_{lang}'] = self.get_descripcion_ttt(
                        place_element)

                if place[f'stars'] is None:
                    place[f'stars'] = self.get_stars(
                        place_element)

                if place[f'imagenes'] == []:
                    place[f'imagenes'] = self.get_imagenes()

                maps_data = MapsScraper(args.verbose).scrape(
                    self.driver, place, lang)

                if maps_data is not None:
                    for place_key in place.keys():
                        if place[place_key] is None or place[place_key] == [] or place[place_key] == {}:
                            if place_key in maps_data and (maps_data[place_key] is not None or maps_data[place_key] != [] or maps_data[place_key] != {}):
                                place[place_key] = maps_data[place_key]

                self.scrape_by_language_new_tab(
                    territory, place, 'en' if lang == 'es' else 'es')

                final = {}

                final['name'] = place['nombre_place_es']
                final['nameEn'] = place['nombre_place_en']
                final['place'] = place['direccion_es']
                final['placeEn'] = place['direccion_en']
                final['location'] = [territory['_id']]
                final['stars'] = '' if place['stars'] is None else place['stars']
                final['duration'] = 1 if place['duration'] is None else place['duration']
                final['workingH'] = place['workingH']
                final['tags'] = self.get_tags(place, territory)
                final['classes'] = self.get_classes()
                final['hide'] = False
                final['lat'] = place['lat']
                final['lon'] = place['lon']
                final['web'] = '' if place['web'] is None else place['web']
                final['mail'] = '' if place['mail'] is None else place['mail']
                final['telf'] = '' if place['telf'] is None else place['telf']
                final['createdAt'] = str(datetime.now())
                final['updatedAt'] = str(datetime.now())
                final['elapsed_time'] = time.time() - start_time
                final['durationNull'] = place['duration'] is None
                final['GoogleActivite'] = ''
                final['googlePlaceId'] = place['googlePlaceId']
                final['prices'] = {}
                final['pricesEn'] = {}
                final['priceType'] = '$'
                final['reviews'] = place['reviews_es']
                final['reviewsEn'] = place['reviews_en']

                # ideal cases
                if place['descripcion_ttt_es'] is not None:
                    final['title'] = place['descripcion_ttt_es']

                if place['descripcion_ttt_en'] is not None:
                    final['titleEn'] = place['descripcion_ttt_en']

                if place['descripcion_long_es'] is not None:
                    final['descriptionLarge'] = place['descripcion_long_es']

                if place['descripcion_long_en'] is not None:
                    final['descriptionEn'] = place['descripcion_long_en']

                # edge cases
                if final['title'] is None and place['descripcion_short_es'] is not None:
                    final['title'] = place['descripcion_short_es']

                if final['titleEn'] is None and place['descripcion_short_en'] is not None:
                    final['titleEn'] = place['descripcion_short_en']

                if final['title'] is None or final['title'] == '':
                    final['title'] = final['name']

                if final['titleEn'] is None or final['titleEn'] == '':
                    final['titleEn'] = final['nameEn']

                if len(place['imagenes']) > 0:
                    final['urlImg'] = place['imagenes'][0]
                    final['urlImages'] = place['imagenes']

                try:
                    self.client[os.getenv(
                        'MONGODB_DBNAME_PLACES_COLLECTION_NAME')].insert_one(final)
                except Exception as e:
                    print(e)
                    print(final)
                    time.sleep(2)
                    if self.check_attraction_repeated(place, territory, lang):
                        continue

                print(
                    f"Scraped: \"{final['name']}\" from {self.get_territory_name(territory)}")

            return True

        def scrape(self):
            self.territories = self.get_places_to_scrape()
            self.done = len(self.territories) == 0

            for territory in self.territories:
                self.init_driver()
                if self.scrape_territory(territory):
                    self.set_scraped(territory)

                try:
                    self.driver.backend.storage.clear_requests()
                except:
                    pass
                self.driver.close()

        def run(self):
            while not self.done:
                try:
                    self.scrape()
                except Exception as e:
                    if args.verbose:
                        print(e)
                        traceback.print_exc()
                    if self.driver is not None:
                        try:
                            try:
                                self.driver.backend.storage.clear_requests()
                            except:
                                pass
                            self.driver.close()
                        except:
                            if args.verbose:
                                print(e)

    task = ScrapingThread(idx)
    task.run()


if __name__ == "__main__":
    print(f'Starting {thread_count} threads')
    for i in range(thread_count):
        threads.append(Process(target=init, args=(i,)))
        threads[i].start()

    for i in range(thread_count):
        threads[i].join()
