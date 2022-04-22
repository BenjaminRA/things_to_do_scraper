import json
import time
import os
import random
import sys
from typing import final
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
import mysql.connector
import threading
load_dotenv()

thread_count = 1

if (len(sys.argv) > 1):
    try:
        thread_count = int(sys.argv[1])
    except:
        print('Invalid number for thread count')
        sys.exit(1)


class element_has_loaded_suggestions(object):
    def __call__(self, driver):
        return len(driver.find_elements(By.CSS_SELECTOR, '.XOeJFd.rHFvzd ul')) > 0 or len(driver.find_elements(By.CSS_SELECTOR, '.XOeJFd.rHFvzd .rZ2Tg')) > 0


mydb = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci"
)

cursor = mydb.cursor(dictionary=True)

cursor.execute("SELECT * FROM paises")

paises = cursor.fetchall()

for i in range(len(paises)):
    cursor.execute(
        f"select * from departamentos d where d.paises_idpais = {paises[i]['idpais']}")
    departamentos = cursor.fetchall()
    for j in range(len(departamentos)):
        cursor.execute(
            f"select * from ciudades c where c.departamentos_iddepartamento = {departamentos[j]['iddepartamento']} and c.idciudad not in (select idciudad from cache)")
        ciudades = cursor.fetchall()
        random.shuffle(ciudades)
        departamentos[j]['ciudades'] = ciudades

    random.shuffle(departamentos)
    paises[i]['departamentos'] = departamentos

random.shuffle(paises)


def check_if_cached(cursor, idciudad):
    cursor.execute(f"SELECT * FROM cache WHERE idciudad = {idciudad}")
    exists = cursor.fetchall()
    return len(exists) > 0


def add_cached(mydb, cursor, idciudad):
    cursor.execute(f"INSERT INTO cache(idciudad) VALUES ({idciudad})")
    mydb.commit()


def shuffle_paises():
    aux = paises.copy()
    for i in range(len(paises)):
        for j in range(len(paises[i]['departamentos'])):
            random.shuffle(paises[i]['departamentos'][j]['ciudades'])
        random.shuffle(paises[i]['departamentos'])
    random.shuffle(paises)
    return aux


class ScrapingThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.url = 'https://www.google.com/travel/things-to-do?g2lb=2502548,2503771,2503781,4258168,4270442,4284970,4291517,4306835,4597339,4640247,4649665,4680677,4722435,4722900,4723331,4733969,4734960,4738607,4743123,4746263,4752417&hl=es-419&gl=cl&ssta=1&dest_mid=/m/06hkdl&dest_state_type=main&dest_src=ts&q=google+things+to+do&sa=X&ved=2ahUKEwiiibzp4aH3AhVwGbkGHf-TCccQuL0BegQIAxAa'
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
        self.paises = shuffle_paises()

    def scrape(self):
        global cached, cached_mutex

        self.driver = webdriver.Chrome()
        self.done = False

        for pais in self.paises:
            for departamento in pais['departamentos']:
                for ciudad in departamento['ciudades']:
                    print(
                        f"{pais['nombre_pais']} - {departamento['nombre_departamento']} - {ciudad['nombre_ciudad']}")

                    if (check_if_cached(self.cursor, ciudad['idciudad'])):
                        print('City already cached')
                        continue

                    self.driver.get(self.url)
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

                    if len(suggestions) > 0:
                        for suggestion in suggestions:
                            if departamento['nombre_departamento'].lower().strip() in suggestion.text.lower().strip():
                                match = suggestion
                                break

                            if pais['nombre_pais'].lower().strip() in suggestion.text.lower().strip():
                                match = suggestion
                                break

                        if match is not None:
                            match.click()

                            self.driver.execute_script("""
                                var element = document.querySelector(".kQb6Eb");
                                if (element)
                                    element.parentNode.removeChild(element);
                            """)

                            try:
                                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, '.kQb6Eb')))
                            except:
                                add_cached(ciudad['idciudad'])
                                continue

                            self.driver.execute_script("""
                                var element = document.querySelector(".kQb6Eb");
                                if (element)
                                    element.parentNode.removeChild(element);
                            """)

                            self.driver.find_element(
                                By.CSS_SELECTOR, 'button[class="VfPpkd-LgbsSe VfPpkd-LgbsSe-OWXEXe-INsAgc VfPpkd-LgbsSe-OWXEXe-Bz112c-M1Soyc VfPpkd-LgbsSe-OWXEXe-dgl2Hf Rj2Mlf OLiIxf PDpWxe qfvgSe J3Eqid"]').click()

                            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(
                                (By.CSS_SELECTOR, '.kQb6Eb')))

                            places = self.driver.find_elements(
                                By.CSS_SELECTOR, '.kQb6Eb .rbj0Ud.AdWm1c')

                            self.cursor.execute(
                                f"DELETE FROM places where ciudades_idciudad = {ciudad['idciudad']}")
                            self.mydb.commit()
                            values = []
                            for place in places:
                                values.append((ciudad['idciudad'], place.text))

                            self.cursor.executemany(
                                "INSERT INTO places(ciudades_idciudad, nombre_place) VALUES (%s, %s)", values)
                            self.mydb.commit()
                            print(
                                f"{ciudad['nombre_ciudad']} -> {self.cursor.rowcount} places inserted")

                    add_cached(self.mydb, self.cursor, ciudad['idciudad'])

        self.done = True
        self.driver.close()

    def run(self):
        while not self.done:
            try:
                self.scrape()
            except Exception as e:
                print(e)
                if self.driver is not None:
                    try:
                        self.driver.close()
                    except:
                        print(e)


threads = []

print('Starting threads')
for i in range(thread_count):
    threads.append(ScrapingThread())
    threads[i].start()

while True:
    pass
