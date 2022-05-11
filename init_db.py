import os
import argparse
import random
import traceback
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.window import WindowTypes
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from datetime import datetime
from pymongo import InsertOne, DeleteMany, ReplaceOne, UpdateOne
import mysql.connector
from db.mongodb import get_client
from multiprocessing import Process
load_dotenv()

parser = argparse.ArgumentParser()

parser.add_argument('--threads', type=int, default=1,
                    help='Number of threads to run (default: 1)')
parser.add_argument('--fresh', type=bool, default=False,
                    help='Perform database reset (default: False)')
parser.add_argument('--offset', type=int, default=0,
                    help='Windows X position offset. (default: 0)')

args = parser.parse_args()

thread_count = args.threads

threads = []


def init(idx):
    class TranslatorThread():

        def __init__(self, idx):
            self.url = 'https://www.google.com/travel/things-to-do?hl=es-419&dest_mid=%2Fm%2F01qgv7'
            self.driver = None
            self.done = False
            self.daemon = True
            self.client = None
            self.options = webdriver.ChromeOptions()
            self.options.add_argument(
                f"window-position={args.offset + (idx)*400},0")

        def get_places(self):
            places = list(self.client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].find(
                {'translated': False}).limit(5000))
            random.shuffle(places)

            return places

        def check_if_cached(self, word):
            return self.client.translations.find_one({'word': word})

        def get_translation(self, word):
            cached = self.check_if_cached(word)
            if cached is not None:
                return cached['translation']

            input_word = self.driver.find_element(
                By.CSS_SELECTOR, 'textarea')

            input_word.clear()
            input_word.send_keys(Keys.CONTROL + "a")
            input_word.send_keys(Keys.DELETE)

            action = ActionChains(self.driver)
            action.double_click(input_word)

            for letter in word:
                action.send_keys(letter)
            action.perform()

            self.driver.execute_script("""
                var element = document.querySelector(".Q4iAWc");
                if (element)
                    element.parentNode.removeChild(element);
            """)

            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '.Q4iAWc')))

            translated_word = self.driver.find_element(
                By.CSS_SELECTOR, '.Q4iAWc').text.strip()

            self.client.translations.insert_one({
                'word': word,
                'translation': translated_word
            })

            return translated_word

        def translate_place(self, place):
            if place['countryEn'] is not None:
                place['country'] = self.get_translation(place['countryEn'])

            if place['stateEn'] is not None:
                place['state'] = self.get_translation(place['stateEn'])

            if place['cityEn'] is not None:
                place['city'] = self.get_translation(place['cityEn'])

            fullName = place['country']
            if place['state'] is not None:
                fullName += ', ' + place['state']
            if place['city'] is not None:
                fullName += ', ' + place['city']

            place['fullName'] = fullName
            place['translated'] = True

            self.client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].replace_one(
                {'_id': place['_id']}, place)

        def scrape(self):
            self.client = get_client()
            self.places = self.get_places()
            self.done = len(self.places) == 0
            self.driver = webdriver.Chrome(chrome_options=self.options)
            self.driver.get('https://translate.google.cl/?sl=en&tl=es')

            for place in self.places:
                if not self.client[os.getenv(
                        'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].find_one({'_id': place['_id']})['translated']:
                    self.translate_place(place)

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
                            self.driver = webdriver.Chrome(
                                chrome_options=self.options)
                        except:
                            print(e)
            if self.driver is not None:
                try:
                    self.driver.close()
                except:
                    print(e)

    task = TranslatorThread(idx)
    task.run()


if __name__ == '__main__':
    if args.fresh:
        confirm = input(
            'Are you sure you want to delete all data from the database? (y/n) ')

        confirm = 'y'

        if confirm.lower() == 'y':
            client = get_client()

            print('Deleting adminsplaces from database...')
            client[os.getenv(
                'MONGODB_DBNAME_PLACES_COLLECTION_NAME')].delete_many({})

            print('Deleting ciudadcoors from database...')
            client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].delete_many({})

            countries = client.ciudadcoors_raw.find({}).sort('id', 1)
            requests = []

            for country in countries:
                requests.append(InsertOne({
                    'city': None,
                    'state': None,
                    'country': country['name'],
                    'fullName': country['name'],
                    'createdAt': str(datetime.now()),
                    'updatedAt': str(datetime.now()),
                    'cityEn': None,
                    'stateEn': None,
                    'countryEn': country['name'],
                    'fullNameEn': country['name'],
                    'priceTypedefault': country['currency_symbol'],
                    'lat': float(country['latitude']) if country['latitude'] is not None else None,
                    'lon': float(country['longitude']) if country['longitude'] is not None else None,
                    'emoji': {
                        'emoji': country['emoji'],
                    },
                    'translated': False,
                    'scraped': False
                }))
                for state in country['states']:
                    requests.append(InsertOne({
                        'city': None,
                        'state': state['name'],
                        'country': country['name'],
                        'fullName': state['name'] + ', ' + country['name'],
                        'createdAt': str(datetime.now()),
                        'updatedAt': str(datetime.now()),
                        'cityEn': None,
                        'stateEn': state['name'],
                        'countryEn': country['name'],
                        'fullNameEn': state['name'] + ', ' + country['name'],
                        'priceTypedefault': country['currency_symbol'],
                        'lat': float(state['latitude']) if state['latitude'] is not None else None,
                        'lon': float(state['longitude']) if state['longitude'] is not None else None,
                        'emoji': {
                            'emoji': country['emoji'],
                        },
                        'translated': False,
                        'scraped': False
                    }))
                    for city in state['cities']:
                        requests.append(InsertOne({
                            'city': city['name'],
                            'state': state['name'],
                            'country': country['name'],
                            'fullName': city['name'] + ', ' + state['name'] + ', ' + country['name'],
                            'createdAt': str(datetime.now()),
                            'updatedAt': str(datetime.now()),
                            'cityEn': city['name'],
                            'stateEn': state['name'],
                            'countryEn': country['name'],
                            'fullNameEn': city['name'] + ', ' + state['name'] + ', ' + country['name'],
                            'priceTypedefault': country['currency_symbol'],
                            'lat': float(city['latitude']) if city['latitude'] is not None else None,
                            'lon': float(city['longitude']) if city['longitude'] is not None else None,
                            'emoji': {
                                'emoji': country['emoji'],
                            },
                            'translated': False,
                            'scraped': False
                        }))

            client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].bulk_write(requests)

    for i in range(thread_count):
        threads.append(Process(target=init, args=(i,)))
        threads[i].start()

    for i in range(thread_count):
        threads[i].join()
