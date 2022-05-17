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
from db.mongodb import get_client_by_host
from multiprocessing import Process
load_dotenv()

parser = argparse.ArgumentParser()

parser.add_argument('--threads', type=int, default=1,
                    help='Number of threads to run (default: 1)')
parser.add_argument('--offset', type=int, default=0,
                    help='Windows X position offset. (default: 0)')

args = parser.parse_args()

thread_count = args.threads

threads = []
NOT_FIXED_QUERY = {'$or': [{'fixed': False},
                           {'incomplete': {'$exists': False}}]}


def init(idx):
    class FixesThread():

        def __init__(self, idx):
            self.done = False
            self.daemon = True
            self.current_client = None

        def get_places(self, client):
            places = list(client[os.getenv(
                'MONGODB_DBNAME_PLACES_COLLECTION_NAME')].find(NOT_FIXED_QUERY).limit(500))
            random.shuffle(places)

            return places

        def get_cities(self, client):
            places = list(client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].find(
                {'fixed': False}).limit(500))
            random.shuffle(places)

            return places

        def fix_city(self, city, client):
            city['radius'] = 8000
            city['airportCoord'] = {
                'lat': city['lat'],
                'lon': city['lon']
            }
            fullName = []
            if 'city' in city and city['city'] is not None:
                fullName.append(city['city'])
            if 'state' in city and city['state'] is not None:
                fullName.append(city['state'])
            if 'country' in city and city['country'] is not None:
                fullName.append(city['country'])

            city['fullName'] = ', '.join(fullName)
            city['fixed'] = True

            client[os.getenv('MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].replace_one(
                {'_id': city['_id'], 'fixed': False}, city)

        def get_urlId(self, place):
            urlId = []
            codeId = str(place['_id'])[-5:]

            if 'name' in place and place['name'] is not None:
                esId = f"{codeId}-{place['name'].replace(' ', '-')}"
                urlId.append(esId)

            if 'nameEn' in place and place['nameEn'] is not None:
                enId = f"{codeId}-{place['nameEn'].replace(' ', '-')}"
                if enId != esId:
                    urlId.append(enId)

            return urlId

        def add_zero_to_time(self, time):
            if len(time) == 4:
                return '0' + time
            return time

        def fix_place(self, place, client):
            incomplete_fields = []

            workingH_null = {
                '2022-05-05': {
                    '1_7': {
                        'start': '0:00',
                        'end': '23:59',
                        'gap': {}
                    }
                }
            }
            workingH_placeholder = {
                '2022-05-05': {
                    '1_7': {
                        'start': '00:00',
                        'end': '00:00',
                        'gap': {}
                    }
                }
            }
            if place['fixed']:
                if place['workingH'] == workingH_null:
                    place['workingH'] = workingH_placeholder
                    incomplete_fields.append('workingH')
                else:
                    for key in place['workingH']['2022-05-05'].keys():
                        place['workingH']['2022-05-05'][key]['start'] = self.add_zero_to_time(
                            place['workingH']['2022-05-05'][key]['start'])
                        place['workingH']['2022-05-05'][key]['end'] = self.add_zero_to_time(
                            place['workingH']['2022-05-05'][key]['end'])

                        if place['workingH']['2022-05-05'][key]['gap'] != {}:
                            place['workingH']['2022-05-05'][key]['gap']['start'] = self.add_zero_to_time(
                                place['workingH']['2022-05-05'][key]['gap']['start'])
                            place['workingH']['2022-05-05'][key]['gap']['end'] = self.add_zero_to_time(
                                place['workingH']['2022-05-05'][key]['gap']['end'])
            else:
                if place['workingH'] == {}:
                    place['workingH'] = workingH_placeholder
                    incomplete_fields.append('workingH')
                else:
                    for key in place['workingH'].keys():
                        place['workingH'][key]['start'] = self.add_zero_to_time(
                            place['workingH'][key]['inicio'])
                        place['workingH'][key]['end'] = self.add_zero_to_time(
                            place['workingH'][key]['fin'])

                        if place['workingH'][key]['gap'] != {}:
                            place['workingH'][key]['gap']['start'] = self.add_zero_to_time(
                                place['workingH'][key]['gap']['inicio'])
                            place['workingH'][key]['gap']['end'] = self.add_zero_to_time(
                                place['workingH'][key]['gap']['fin'])

                            del place['workingH'][key]['gap']['inicio']
                            del place['workingH'][key]['gap']['fin']

                        del place['workingH'][key]['inicio']
                        del place['workingH'][key]['fin']

                place['workingH'] = {
                    '2022-05-05': place['workingH']
                }

            if 'placeEn' in place:
                del place['placeEn']

            if place['urlImg'] == None:
                incomplete_fields.append('urlImg')

            if place['title'] == place['name']:
                incomplete_fields.append('title')

            if place['stars'] == '' or place['stars'] == None:
                incomplete_fields.append('stars')

            if place['place'] == '' or place['place'] == None:
                incomplete_fields.append('place')

            place['fixed'] = True
            place['incomplete_fields'] = incomplete_fields
            place['incomplete'] = len(incomplete_fields) > 0
            place['urlId'] = self.get_urlId(place)

            client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].replace_one(
                {**{'_id': place['_id']}, **NOT_FIXED_QUERY}, place)

        def scrape(self):
            hosts = [
                'mining.wmjx2.mongodb.net',
                'mining.jnmve.mongodb.net',
                'mining.9enqq.mongodb.net',
                'mining.5qsxj.mongodb.net',
                'mining.qmm0p.mongodb.net',
                'mining.lt4yb.mongodb.net',
                'mining.7ycgq.mongodb.net',
                'mining.eyrxk.mongodb.net',
                'mining.jgqac.mongodb.net',
                'mining.qdxqh.mongodb.net',
                'mining.fgwlp.mongodb.net',
            ]

            for host in hosts:
                client = get_client_by_host(host)

                not_done = 1
                while not_done > 0:
                    cities = self.get_cities(client)
                    places = self.get_places(client)

                    for city in cities:
                        self.fix_city(city, client)

                    for place in places:
                        self.fix_place(place, client)

                    not_done = len(cities) + len(places)

            self.done = True

        def run(self):
            while not self.done:
                try:
                    self.scrape()
                except Exception as e:
                    print(e)
                    traceback.print_exc()

    task = FixesThread(idx)
    task.run()


if __name__ == '__main__':

    for i in range(thread_count):
        threads.append(Process(target=init, args=(i,)))
        threads[i].start()

    for i in range(thread_count):
        threads[i].join()
