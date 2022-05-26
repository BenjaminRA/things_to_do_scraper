import json
import math
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
NOT_FIXED_CITIES_QUERY = {'radioBoundaries': {'$exists': False}}
TO_HIDE = json.load(open('to_hide.json', encoding="utf-8"))


def init(idx):
    class FixesThread():

        def __init__(self, idx):
            self.done = False
            self.daemon = True
            self.current_client = None

        def get_cities(self, client):
            places = list(client[os.getenv(
                'MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].aggregate([
                    {'$match': NOT_FIXED_CITIES_QUERY},
                    {'$sample': {'size': 1000}}
                ]))
            random.shuffle(places)

            return places

        def get_boundaries(self, city, distance=1):
            # Javascript to python
            # const degs2Rads = deg => (deg * Math.PI) / 180.0;
            # const rads2Degs = rad => rad * 180 / Math.PI;

            def degs2Rads(deg): return (deg * math.pi) / 180.0
            def rads2Degs(rad): return rad * 180 / math.pi

            earthRadius = 6371
            response = {}
            cardinalCoords = {
                'north': 0,
                'south': 180,
                'east': 90,
                'west': 270
            }

            rLat = degs2Rads(city['lat'])
            rLng = degs2Rads(city['lon'])
            rAngDist = distance/earthRadius

            for cardinal in cardinalCoords:
                rAngle = degs2Rads(cardinalCoords[cardinal])
                rLatB = math.asin(math.sin(rLat) * math.cos(rAngDist) +
                                  math.cos(rLat) * math.sin(rAngDist) * math.cos(rAngle))
                rLonB = rLng + math.atan2(math.sin(rAngle) * math.sin(rAngDist) * math.cos(
                    rLat), math.cos(rAngDist) - math.sin(rLat) * math.sin(rLatB))

                response[cardinal] = {
                    'lat': rads2Degs(rLatB),
                    'lng': rads2Degs(rLonB)
                }

            return {
                'min_lat': response['south']['lat'],
                'max_lat': response['north']['lat'],
                'min_lng': response['west']['lng'],
                'max_lng': response['east']['lng']
            }

        def add_location_to_attraction(self, place, city, client):
            set_query = {}
            temp = place['location']
            if city['_id'] not in temp:
                temp.append(city['_id'])

            set_query['location'] = temp
            set_query['updatedAt'] = str(datetime.now())

            client[os.getenv(
                'MONGODB_DBNAME_PLACES_COLLECTION_NAME')].update_one({
                    '_id': place['_id']
                }, {
                    '$set': set_query
                })

        def get_activities_in_area(self, city, clients):
            count = 0
            for client in clients:
                result = list(client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].aggregate([
                    {
                        '$match': {
                            'incomplete': False,
                            'hide': False,
                            'lat': {'$gte': city['radioBoundaries']['min_lat'], '$lte': city['radioBoundaries']['max_lat']},
                            'lon': {'$gte': city['radioBoundaries']['min_lng'], '$lte': city['radioBoundaries']['max_lng']}
                        }
                    }
                ]))

                for place in result:
                    self.add_location_to_attraction(place, city, client)

                count += len(result)

            return count

        def fix_city(self, city, clients):
            for client in clients:
                city_temp = client[os.getenv('MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].find_one(
                    {'_id': city['_id']})
                if 'radioBoundaries' in city_temp and city_temp['radioBoundaries'] is not None:
                    return

            start_time = time.time()

            if 'radioBoundaries' not in city or city['radioBoundaries'] is None:
                city['radioBoundaries'] = self.get_boundaries(city, 25)
                self.get_activities_in_area(city, clients)

                if city['fullName'].lower() in TO_HIDE:
                    city['numberActivities'] = 0
                else:
                    count = 0
                    for client in clients:
                        places_count = list(client[os.getenv('MONGODB_DBNAME_PLACES_COLLECTION_NAME')].aggregate([
                            {
                                '$match': {
                                    'location': {'$in': [city['_id']]},
                                    'incomplete': False,
                                    'hide': False
                                }
                            }, {
                                '$count': 'atracciones'
                            }
                        ]))

                        count += (0 if len(
                            places_count) == 0 else places_count[0]['atracciones'])

                    city['numberActivities'] = count

            for client in clients:
                client[os.getenv('MONGODB_DBNAME_CIUDADES_COLLECTION_NAME')].replace_one(
                    {**{'_id': city['_id']}, **NOT_FIXED_CITIES_QUERY}, city)

            print(f"{city['fullName']}: {time.time() - start_time} [s]")

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
                    # Since the cities are the same in all the hosts of the same group, we fetch from the first one
                    cities = self.get_cities(clients[0])

                    # For each city, we get the places and we fix them
                    for city in cities:
                        self.fix_city(city, clients)

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
