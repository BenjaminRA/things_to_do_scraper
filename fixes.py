import json
import os
import argparse
import random
import time
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

NOT_FIXED_CITIES_QUERY = {'$or': [
    {'fixed': False},
    {'numberActivities': {'$exists': False}},
    {'priority': {'$exists': False}},
    {'$and': [{'numberActivities': {'$gte': 3}}, {
        'activitiesImg.2': {'$exists': False}}]},
    {'lat': {'$exists': True}},
    {'autoCompleteSelector': {'$exists': False}},
]}

TO_HIDE = json.load(open('to_hide.json', encoding="utf-8"))
EMOJI_CITY = json.load(open('emojicities.json', encoding="utf-8"))


def init(idx):
    class FixesThread():

        def __init__(self, idx):
            self.done = False
            self.daemon = True
            self.current_client = None

        def get_places(self, client):
            places = list(client[os.getenv(
                'MONGODB_DBNAME_PLACES_COLLECTION_NAME')].aggregate([
                    {'$match': NOT_FIXED_QUERY},
                    {'$sample': {'size': 1000}}
                ]))
            random.shuffle(places)

            return places

        def get_cities(self, client):
            places = list(client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].aggregate([
                    {'$match': NOT_FIXED_CITIES_QUERY},
                    {'$sample': {'size': 1000}}
                ]))
            random.shuffle(places)

            return places

        def get_priority(self, numberActivities):
            if numberActivities > 50:
                return 4

            if numberActivities > 20 and numberActivities <= 50:
                return 3

            if numberActivities >= 10 and numberActivities <= 20:
                return 2

            if numberActivities >= 5 and numberActivities < 10:
                return 1

            return 0

        def fix_city(self, city, clients):
            for client in clients:
                city_temp = client[os.getenv('MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].find_one(
                    {'_id': city['_id']})
                if 'activitiesImg' in city_temp and len(city_temp['activitiesImg']) == 3:
                    return

            start_time = time.time()
            if 'fixed' not in city or not city['fixed']:
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

            if 'numberActivities' not in city:
                if city['fullName'].lower() in TO_HIDE:
                    city['numberActivities'] = 0
                else:

                    count = 0
                    for client in clients:
                        places_count = list(client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].aggregate([
                            {
                                '$match': {'location': {'$in': [city['_id']]}, 'incomplete': False, 'hide': False}
                            }, {
                                '$count': 'atracciones'
                            }
                        ]))

                        count += (0 if len(
                            places_count) == 0 else places_count[0]['atracciones'])

                    city['numberActivities'] = count

            if f"{city['countryEn'].lower()} flag" in EMOJI_CITY:
                city['emoji'] = EMOJI_CITY[f"{city['countryEn'].lower()} flag"]

            if 'priority' not in city:
                count = 0
                for client in clients:
                    places_count = list(client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].aggregate([
                        {
                            '$match': {'location': {'$in': [city['_id']]}}
                        }, {
                            '$count': 'atracciones'
                        }
                    ]))

                    count += (0 if len(
                        places_count) == 0 else places_count[0]['atracciones'])

                city['numberActivitiesTotal'] = count
                city['priority'] = self.get_priority(count)

            if 'activitiesImg' not in city or len(city['activitiesImg']) < 3:
                images = []
                if city['numberActivities'] > 0:

                    places = list(client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].aggregate([
                        {
                            '$match': {
                                'location': {'$in': [city['_id']]},
                                'incomplete': False,
                                'urlImg': {'$ne': None}
                            }
                        }, {
                            '$sort': {'stars': -1, '_id': 1}
                        }, {
                            '$limit': 3
                        }
                    ]))

                    for place in places:
                        images.append(place['urlImg'])

                city['activitiesImg'] = images

            if 'autoCompleteSelector' not in city:
                autoCompleteSelectorArray = []
                if 'city' in city and city['city'] is not None:
                    autoCompleteSelectorArray.append(city['city'])
                if 'country' in city and city['country'] is not None:
                    autoCompleteSelectorArray.append(city['country'])
                if 'cityEn' in city and city['cityEn'] is not None:
                    autoCompleteSelectorArray.append(city['cityEn'])
                if 'countryEn' in city and city['countryEn'] is not None:
                    autoCompleteSelectorArray.append(city['countryEn'])

                city['autoCompleteSelector'] = " ".join(
                    autoCompleteSelectorArray).lower()

            for client in clients:
                client[os.getenv('MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].replace_one(
                    {**{'_id': city['_id']}, **NOT_FIXED_CITIES_QUERY}, city)

            print(f"{city['fullName']}: {time.time() - start_time} [s]")

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

            if 'urlImg' not in place or place['urlImg'] == None or place['urlImg'] == '':
                incomplete_fields.append('urlImg')

            if place['title'] == place['name']:
                incomplete_fields.append('title')

            if 'stars' not in place or place['stars'] == '' or place['stars'] == None:
                incomplete_fields.append('stars')

            if 'place' not in place or place['place'] == '' or place['place'] == None:
                incomplete_fields.append('place')

            place['fixed'] = True
            place['incomplete_fields'] = incomplete_fields
            place['incomplete'] = len(incomplete_fields) > 0
            place['urlId'] = self.get_urlId(place)

            client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].replace_one(
                {**{'_id': place['_id']}, **NOT_FIXED_QUERY}, place)

        def scrape(self):
            hosts = [
                ['tripendar.qao9p.mongodb.net']
                # ['mining.wmjx2.mongodb.net'],
                # ['mining.jnmve.mongodb.net'],
                # ['mining.9enqq.mongodb.net', 'mining.5qsxj.mongodb.net'],
                # ['mining.qmm0p.mongodb.net', 'mining.lt4yb.mongodb.net'],
                # ['mining.7ycgq.mongodb.net', 'mining.eyrxk.mongodb.net'],
                # ['mining.jgqac.mongodb.net'],
                # ['mining.qdxqh.mongodb.net'],
                # ['mining.fgwlp.mongodb.net'],
            ]

            random.shuffle(hosts)

            for host in hosts:
                clients = []

                # Create a client for each host
                for url in host:
                    clients.append(get_client_by_host(url))

                not_done = 1
                while not_done > 0:
                    # Get places in different arrays to know what set of places corresponds to what client
                    places_array = []
                    for client in clients:
                        places_array.append([self.get_places(client)])
                        not_done += len(places_array[-1])

                    # Since the cities are the same in all the hosts of the same group, we fetch from the first one
                    cities = self.get_cities(clients[0])

                    # For each city, we get the places and we fix them
                    for city in cities:
                        self.fix_city(city, clients)

                    # For each set of places, we call the fix_place function with the place
                    # and the corresponding client where the place lives
                    for places in places_array:
                        for i in range(len(places)):
                            for place in places[i]:
                                pass
                                # self.fix_place(place, clients[i])

                    not_done = len(cities)

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
