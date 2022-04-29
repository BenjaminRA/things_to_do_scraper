import json
import time
import os
import random
import sys
import traceback
import requests
import re
from lxml.html import fromstring
from itertools import cycle
from multiprocessing import Process
from typing import final
from dotenv import load_dotenv
from seleniumwire import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.window import WindowTypes
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
import mysql.connector
load_dotenv()


class MapsScraper():

    def __init__(self):
        self.driver = None
        self.data = {}
        self.json_data = {}
        self.lang = ''

    def init_driver(self):
        if self.driver is not None:
            try:
                self.driver.close()
            except:
                pass
        options = webdriver.ChromeOptions()
        # options.add_argument('window-position=2560,0')
        options.add_argument('window-position=960,0')
        options.add_experimental_option(
            'prefs', {'intl.accept_languages': 'en-GB' if self.lang == 'en' else 'es-ES'})

        self.driver = webdriver.Chrome(chrome_options=options)

    def wait_for_element(self, selector):
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector)))

    def get_json(self):
        self.json_data = {}
        try:
            raw_json = self.driver.execute_script(
                'return window.APP_INITIALIZATION_STATE[3][6].substring(5)')

            self.json_data = json.loads(raw_json)[6]

        except Exception as e:
            print(e)
            traceback.print_exc()

    def get_direccion(self, lang):
        try:
            self.data[f'direccion_{lang}'] = ', '.join(self.json_data[2])
        except Exception as e:
            print(f'direccion not found')
            # print(e)
            # traceback.print_exc()

    def get_web(self):
        try:
            self.data[f'web'] = self.json_data[7][1]
        except Exception as e:
            print(f'web not found')
            # print(e)
            # traceback.print_exc()

    def get_telefono(self):
        try:
            # element = self.driver.find_elements(
            #     By.CSS_SELECTOR, 'button[data-item-id^="phone:tel:"] .Io6YTe')

            # if len(element) > 0:
            #     element = element[0]
            #     self.data[f'telefono'] = element.text
            self.data[f'telefono'] = self.json_data[178][0][0]
        except Exception as e:
            print(f'telefono not found')
            # print(e)
            # traceback.print_exc()

    def get_horarios(self):
        try:
            element = self.driver.find_elements(
                By.CSS_SELECTOR, '.LJKBpe-Tswv1b-hour-text')

            if len(element) > 0:
                element = element[0]
                element.click()

                temp = {}

                days_map = {
                    'lunes': 'monday',
                    'martes': 'tuesday',
                    'miercoles': 'wednesday',
                    'miércoles': 'wednesday',
                    'jueves': 'thursday',
                    'viernes': 'friday',
                    'sabado': 'saturday',
                    'sábado': 'saturday',
                    'domingo': 'sunday',
                    'monday': 'monday',
                    'tuesday': 'tuesday',
                    'wednesday': 'wednesday',
                    'thursday': 'thursday',
                    'friday': 'friday',
                    'saturday': 'saturday',
                    'sunday': 'sunday',
                }

                days = self.driver.find_elements(
                    By.CSS_SELECTOR, '.eK4R0e.tfUnhc tr')

                for day in days:
                    day_name = day.find_element(
                        By.CSS_SELECTOR, '.ylH6lf div:first-child').text.lower().strip()

                    day_times = day.find_elements(
                        By.CSS_SELECTOR, '.mxowUb .G8aQO')
                    day_time = ' - '.join(
                        list(map(lambda x: x.text.lower().strip(), day_times)))

                    temp[days_map[day_name]] = day_time

                self.data['horarios'] = temp

        except Exception as e:
            print(f'horarios not found')
            # print(e)
            # traceback.print_exc()

    def get_coordenadas(self):
        try:
            self.data['lat'] = self.json_data[9][2]
            self.data['lng'] = self.json_data[9][3]

        except Exception as e:
            print(f'coordenadas not found')
            # print(e)
            # traceback.print_exc()

    def get_rating(self):
        try:
            self.data['rating'] = self.json_data[4][7]

        except Exception as e:
            print(f'rating not found')
            # print(e)
            # traceback.print_exc()

    def get_categorias(self):
        try:
            self.data['categorias'] = list(
                map(lambda x: x[0], self.json_data[76]))

        except Exception as e:
            print(f'categorias not found')
            # print(e)
            # traceback.print_exc()

    def get_descripcion(self, lang):
        found = False
        try:
            very_long = self.driver.find_element(
                By.CSS_SELECTOR, '.wEvh0b')
            self.data[f'descripcion_long_{lang}'] = very_long.text
            found = True

        except Exception as e:
            pass
            # print('descripcion not found')

        try:
            self.data[f'descripcion_short_{lang}'] = self.json_data[32][0][1]
            self.data[f'descripcion_long_{lang}'] = self.json_data[32][1][1]
            found = True

        except Exception as e:
            pass
            # print(f'descripcion not found')
            # print(e)
            # traceback.print_exc()

        if not found:
            print('descripcion not found')

    def get_imagenes(self):
        changed_page = False
        try:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.ofKBgf')))

                element = self.driver.find_elements(
                    By.CSS_SELECTOR, '.ofKBgf')

                if len(element) > 0:
                    element = element[0]
                    ActionChains(self.driver).move_to_element(
                        element).perform()
                    element.click()

                    changed_page = True
            except:
                element = self.driver.find_elements(
                    By.CSS_SELECTOR, '.jtJMuf')

                if len(element) > 0:
                    element = element[0]
                    ActionChains(self.driver).move_to_element(
                        element).perform()
                    element.click()

                    changed_page = True
                else:
                    raise Exception('not found')

            images = []

            self.wait_for_element(
                'div[class="onegoogle noprint app-sandbar-vasquette hidden-one-google"]')

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.m6QErb.DxyBCb')))

            photo_elements = self.driver.find_elements(
                By.CSS_SELECTOR, '.m6QErb.DxyBCb .mWq4Rd-HiaYvf-MNynB-gevUs')

            if len(photo_elements) == 0:
                photo_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, '.m6QErb.DxyBCb .U39Pmb')

            for photo in photo_elements:
                bg_image = photo.value_of_css_property(
                    'background-image')

                while bg_image == 'url("https://:0/")':
                    ActionChains(self.driver).move_to_element(
                        photo).perform()

                    time.sleep(0.5)
                    bg_image = photo.value_of_css_property(
                        'background-image')

                bg_image = bg_image.replace(
                    'url(', '').replace(')', '').replace('"', '')
                url = bg_image.replace('lh5', 'lh3').split('=')[
                    0] + '=s0'
                images.append(url)

            self.data['imagenes'] = images

        except Exception as e:
            print(f'imagenes not found')
            # print(e)
            # traceback.print_exc()

        finally:
            if changed_page:
                self.driver.back()
                try:
                    self.wait_for_element(
                        'div[class="onegoogle noprint app-sandbar-vasquette"]')
                except Exception as e:
                    pass

    def get_duracion(self, lang):
        try:
            avg_time_spent = self.json_data[117][0]

            text = avg_time_spent.split(
                'People typically spend up to ' if lang == 'en' else 'Tiempo máximo de permanencia: ')[1]

            self.data['duracion'] = text.replace("\xa0", " ").replace(
                "horas", "hour").replace("minuto", "minute")

        except Exception as e:
            print('duracion not found')
            # print(e)
            # traceback.print_exc()

    def get_reviews(self, lang):
        changed_page = False
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'button[jsaction="pane.reviewlist.goToReviews"]')))

            element = self.driver.find_elements(
                By.CSS_SELECTOR, 'button[jsaction="pane.reviewlist.goToReviews"]')

            if len(element) > 0:
                element = element[0]
                ActionChains(self.driver).move_to_element(
                    element).perform()

                self.driver.execute_script("""
                    var elements = document.querySelectorAll('div[class="m6QErb"][jsan="t-dgE5uNmzjiE,7.m6QErb"]');
                    for (let element of elements) {
                        element.parentNode.removeChild(element);
                    }
                """)

                element.click()

                changed_page = True

                reviews = []

                WebDriverWait(self.driver, 30).until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div[class="m6QErb"][jsan="t-dgE5uNmzjiE,7.m6QErb"]')))

                review_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, 'div[class="m6QErb"][jsan="t-dgE5uNmzjiE,7.m6QErb"] .jftiEf.L6Bbsd')

                for review in review_elements:
                    ActionChains(self.driver).move_to_element(
                        review).perform()

                    author = review.find_element(
                        By.CSS_SELECTOR, '.d4r55').text.strip()

                    rating = review.find_element(By.CSS_SELECTOR, '.kvMYJc').get_attribute(
                        'aria-label').strip().split('\xa0')[0]

                    more_button = review.find_elements(
                        By.CSS_SELECTOR, '.w8nwRe.kyuRq')
                    if len(more_button) > 0:
                        more_button[0].click()

                    text = review.find_element(
                        By.CSS_SELECTOR, '.wiI7pd').text.strip()

                    reviews.append({
                        'author': author,
                        'rating': rating,
                        'review': text
                    })

                self.data[f'reviews_{lang}'] = reviews

        except Exception as e:
            print(f'reviews_{lang} not found')
            # print(e)
            # traceback.print_exc()

        finally:
            if changed_page:
                self.driver.back()
                self.wait_for_element(
                    'div[class="onegoogle noprint app-sandbar-vasquette"]')

    def scrape(self, driver, place, lang):
        if place['place_id'] is None:
            return None

        main_windows_name = driver.window_handles[0]

        try:
            self.place = place
            self.lang = lang

            self.driver = driver

            # self.init_driver()

            self.driver.switch_to.new_window(WindowTypes.TAB)

            self.driver.set_page_load_timeout(60)
            self.driver.get(
                f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}")

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.lMbq3e')))

            self.get_json()

            self.data = {
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

            if self.place['web'] is None:
                self.get_web()

            if self.place['rating'] is None:
                self.get_rating()

            if self.place['telefono'] is None:
                self.get_telefono()

            if self.place['horarios'] == []:
                self.get_horarios()

            if self.place['lat'] is None or self.place['lng'] is None:
                self.get_coordenadas()

            if self.place['duracion'] is None:
                self.get_duracion(self.lang)

            if self.place['imagenes'] == []:
                self.get_imagenes()

            if self.place['categorias'] == []:
                self.get_categorias()

            self.get_descripcion(self.lang)
            self.get_direccion(self.lang)

            self.get_reviews(self.lang)

            if self.driver is not None:
                self.driver.close()
                self.driver.switch_to.window(window_name=main_windows_name)

            return self.data

        except Exception as e:
            print(f'Error scraping {place["place_id"]}')
            print(e)
            traceback.print_exc()

            if self.driver is not None:
                self.driver.close()
                self.driver.switch_to.window(window_name=main_windows_name)

            return None
