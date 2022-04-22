import json
import time
import os
import random
import sys
from dotenv import load_dotenv
import mysql.connector
import threading
import requests
import traceback
from lxml.html import fromstring
from itertools import cycle
load_dotenv()

cached_mutex = threading.Lock()

thread_count = 1

if (len(sys.argv) > 1):
    try:
        thread_count = int(sys.argv[1])
    except:
        print('Invalid number for thread count')
        sys.exit(1)


mydb = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci"
)

cursor = mydb.cursor(dictionary=True)

cursor.execute("""
    SELECT p.*, c.nombre_ciudad, d.nombre_departamento, pa.nombre_pais FROM places p
    JOIN ciudades c on c.idciudad = p.ciudades_idciudad
    JOIN departamentos d on d.iddepartamento = c.departamentos_iddepartamento
    JOIN paises pa on pa.idpais = d.paises_idpais
    WHERE p.info IS NULL 
""")

places = cursor.fetchall()


def shuffle_places():
    aux = places.copy()
    random.shuffle(aux)
    return aux


def get_proxies():
    url = 'https://free-proxy-list.net/'
    response = requests.get(url)
    parser = fromstring(response.text)
    proxies = set()
    for i in parser.xpath('//tbody/tr')[:10]:
        if i.xpath('.//td[7][contains(text(),"yes")]'):
            proxy = ":".join([i.xpath('.//td[1]/text()')[0],
                             i.xpath('.//td[2]/text()')[0]])
            proxies.add(proxy)
    return proxies


proxies = get_proxies()


class MapsScrapingThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
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
        self.places = shuffle_places()
        self.proxy_pool = cycle(proxies)

    def scrape(self):
        global cached, cached_mutex
        self.done = False

        for place in self.places:
            print(place)
            self.cursor.execute(
                f"SELECT * FROM places WHERE info IS NULL and idplace = {place['idplace']}")

            is_empty = self.cursor.fetchall()

            if (len(is_empty) == 0):
                continue

            data = {}
            for lang in ['es-419', 'en']:
                print(f"Scraping {place['nombre_place']} in {lang}")
                url = f"https://www.google.cl/search?q={place['nombre_place']}, {place['nombre_ciudad']}, {place['nombre_departamento']}, {place['nombre_pais']}&tbm=map&hl={lang}"

                proxy = next(self.proxy_pool)
                print(proxy)
                response = requests.get(url, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Content-Type': 'application/json; charset=UTF-8',
                    'Cookie': '1P_JAR=2022-04-18-00; AEC=AakniGMPrXSru5jrixq1vkbR1kj6vxLxTsvoAWdZpXRSHHhEtlSUMvCuRQ; NID=511=AcMEChtrAah9QQ6KZ-VOOFhsmkwuzmknM3BUlge-p18uEfa14TmJubIn4lB4DLRu5Z-kHc_6TFV3gHepzzDrJSLJQSYGoY09WWyqWfrg7fE1t_ScmMleezCwE2u01GtuKYJJOMX6uRdY5sAQxb6A4FulvaMuk5daxpLF9G1OVqQ'
                }, proxies={"http": proxy, "https": proxy})

                # print(response.text)

                json_response = json.loads(response.text[5:])

                temp = {}

                try:
                    temp['name'] = json_response[0][1][0][14][18]
                except:
                    pass

                try:
                    temp['address'] = ', '.join(json_response[0][1][0][14][2])
                except:
                    pass

                try:
                    temp['web'] = json_response[0][1][0][14][7]
                except:
                    pass

                try:
                    temp['telefono'] = json_response[0][1][0][14][178][0][0]
                except:
                    pass

                try:
                    temp['rating'] = json_response[0][1][0][14][4][7]
                except:
                    pass

                try:
                    temp['description'] = {
                        'short': json_response[0][1][0][14][32][0][1],
                        'long': json_response[0][1][0][14][32][1][1]
                    }
                except:
                    pass

                try:
                    temp['coordinates'] = {
                        'lat': json_response[0][1][0][14][9][2],
                        'lng': json_response[0][1][0][14][9][3]
                    }
                except:
                    pass

                try:
                    temp['categories'] = list(
                        map(lambda category: category[0], json_response[0][1][0][14][76]))
                except:
                    pass

                data[lang] = temp

            self.cursor.execute(
                f"UPDATE places SET info = '{json.dumps(data)}', updated_at = CURRENT_TIMESTAMP WHERE idplace = {place['idplace']}")
            self.mydb.commit()
            print(
                f"{place['nombre_place']} -> info inserted")

        self.done = True

    def run(self):
        while not self.done:
            try:
                self.scrape()
            except Exception as e:
                print('Exception:', e)
                traceback.print_exc()


threads = []

print('Starting threads')
for i in range(thread_count):
    threads.append(MapsScrapingThread())
    threads[i].start()

while True:
    pass
