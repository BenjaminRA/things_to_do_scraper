import json
import time
import os
import random
import sys
import traceback
from multiprocessing import Process
from typing import final
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
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

threads = []


def init():
    class element_has_loaded_suggestions(object):
        def __call__(self, driver):
            return len(driver.find_elements(By.CSS_SELECTOR, '.XOeJFd.rHFvzd ul')) > 0 or len(driver.find_elements(By.CSS_SELECTOR, '.XOeJFd.rHFvzd .rZ2Tg')) > 0

    class ScrapingThread():

        def __init__(self):
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
            self.ciudades = []

        def get_ciudades(self):
            self.cursor.execute("""
                SELECT p.nombre_pais, d.nombre_departamento, c.nombre_ciudad, c.idciudad FROM ciudades c 
                JOIN departamentos d ON d.iddepartamento = c.departamentos_iddepartamento
                JOIN paises p ON p.idpais = d.paises_idpais
                WHERE c.idciudad NOT IN (SELECT idciudad FROM cache)
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

        def scrape(self):
            global cached, cached_mutex

            self.ciudades = self.get_ciudades()
            self.driver = webdriver.Chrome()
            self.done = False

            for ciudad in self.ciudades:
                print(
                    f"{ciudad['nombre_pais']} - {ciudad['nombre_departamento']} - {ciudad['nombre_ciudad']}")

                if (self.check_if_cached(ciudad['idciudad'])):
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
                        if ciudad['nombre_departamento'].lower().strip() in suggestion.text.lower().strip():
                            match = suggestion
                            break

                        if ciudad['nombre_pais'].lower().strip() in suggestion.text.lower().strip():
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
                            self.add_cached(ciudad['idciudad'])
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
