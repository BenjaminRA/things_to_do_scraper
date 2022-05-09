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

    def __init__(self, verbose=False):
        self.driver = None
        self.data = {}
        self.json_data = {}
        self.verbose = verbose
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
            if self.verbose:
                print(e)
                traceback.print_exc()

    def get_direccion(self, lang):
        try:
            self.data[f'direccion_{lang}'] = ', '.join(self.json_data[2])
        except Exception as e:
            if self.verbose:
                print(f'direccion not found')

    def get_web(self):
        try:
            self.data[f'web'] = self.json_data[7][1]
        except Exception as e:
            if self.verbose:
                print(f'web not found')

    def get_telf(self):
        try:
            # element = self.driver.find_elements(
            #     By.CSS_SELECTOR, 'button[data-item-id^="phone:tel:"] .Io6YTe')

            # if len(element) > 0:
            #     element = element[0]
            #     self.data[f'telf'] = element.text
            self.data[f'telf'] = self.json_data[178][0][0]
        except Exception as e:
            if self.verbose:
                print(f'telf not found')

    def get_workingH(self):
        try:
            element = self.driver.find_elements(
                By.CSS_SELECTOR, 'img[aria-label="Horario"]')

            if len(element) > 0:
                element = element[0]
                element.click()

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

                days_number_map = {
                    'monday': 1,
                    'tuesday': 2,
                    'wednesday': 3,
                    'thursday': 4,
                    'friday': 5,
                    'saturday': 6,
                    'sunday': 7,
                }

                days = self.driver.find_elements(
                    By.CSS_SELECTOR, '.eK4R0e.tfUnhc tr')

                def extract_date_range(value):
                    if len(value) > 1:
                        return {
                            'inicio': value[0].split('–')[0].strip(),
                            'fin': value[1].split('–')[1].strip(),
                            'gap': {
                                'inicio': value[0].split('–')[1].strip(),
                                'fin': value[1].split('–')[0].strip()
                            }
                        }
                    else:
                        if '24 hours' in value[0] or '24 horas' in value[0]:
                            return {
                                'inicio': '00:00',
                                'fin': '23:59',
                                'gap': {}
                            }
                        else:
                            return {
                                'inicio': value[0].split('–')[0].strip(),
                                'fin': value[0].split('–')[1].strip(),
                                'gap': {}
                            }

                temp = {}

                start_range = ''
                value = []
                last_day = 1

                days = sorted(
                    days, key=lambda x: days_number_map[days_map[x.find_element(
                        By.CSS_SELECTOR, '.ylH6lf div:first-child').text.lower().strip()]])

                for day in days:
                    day_name = day.find_element(
                        By.CSS_SELECTOR, '.ylH6lf div:first-child').text.lower().strip()
                    day_times = day.find_elements(
                        By.CSS_SELECTOR, '.mxowUb .G8aQO')
                    day_times = list(
                        map(lambda x: x.text.lower().strip(), day_times))
                    aux = ' '.join(day_times).lower()
                    day_number = days_number_map[days_map[day_name]]
                    last_day = day_number

                    if len(temp) == 0 and ('cerrado' in aux or 'closed' in aux):
                        continue

                    # start new range
                    if not ('cerrado' in aux or 'closed' in aux):
                        if start_range == '':
                            start_range = day_number

                        if value == []:
                            value = day_times

                    # if range started, end range and start new one
                    if value != day_times:
                        temp[f"{start_range}_{day_number - 1}"] = extract_date_range(
                            value)

                        if 'cerrado' in aux or 'closed' in aux:
                            start_range = ''
                            value = []
                        else:
                            start_range = day_number
                            value = day_times

                if start_range != '':
                    temp[f"{start_range}_{last_day}"] = extract_date_range(
                        value)

                self.data['workingH'] = temp

        except Exception as e:
            if self.verbose:
                print(e)
                traceback.print_exc()
                print(f'workingH not found')

    def get_coordenadas(self):
        try:
            self.data['lat'] = self.json_data[9][2]
            self.data['lon'] = self.json_data[9][3]

        except Exception as e:
            if self.verbose:
                print(f'coordenadas not found')

    def get_stars(self):
        try:
            self.data['stars'] = self.json_data[4][7]

        except Exception as e:
            if self.verbose:
                print(f'stars not found')

    def get_categorias(self):
        try:
            self.data['categorias'] = list(
                map(lambda x: x[0], self.json_data[76]))

        except Exception as e:
            if self.verbose:
                print(f'categorias not found')

    def get_descripcion(self, lang):
        found = False
        try:
            very_long = self.driver.find_element(
                By.CSS_SELECTOR, '.wEvh0b')
            self.data[f'descripcion_long_{lang}'] = very_long.text
            found = True

        except Exception as e:
            if self.verbose:
                print('descripcion not found')

        try:
            self.data[f'descripcion_short_{lang}'] = self.json_data[32][0][1]
            self.data[f'descripcion_long_{lang}'] = self.json_data[32][1][1]
            found = True

        except Exception as e:
            if self.verbose:
                print(f'descripcion not found')

        if not found:
            if self.verbose:
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
            if self.verbose:
                print(f'imagenes not found')

        finally:
            if changed_page:
                self.driver.back()
                try:
                    self.wait_for_element(
                        'div[class="onegoogle noprint app-sandbar-vasquette"]')
                except Exception as e:
                    pass

    def get_duration(self, lang):
        try:
            avg_time_spent = self.json_data[117][0]

            text = avg_time_spent.split(
                'People typically spend up to ' if lang == 'en' else 'Tiempo máximo de permanencia: ')[1] \
                .replace("\xa0", " ") \
                .replace("horas", "hour") \
                .replace("minuto", "minute")

            value = text.split(' ')[0].strip()
            unidad = text.split(' ')[1].strip()

            if 'minute' in unidad or 'min' in unidad:
                value = float(value) / 60

            self.data['duration'] = float(value)

        except Exception as e:
            if self.verbose:
                print('duration not found')

    def get_reviews(self, lang):
        # changed_page = False
        try:
            WebDriverWait(self.driver, 20).until(
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

                # changed_page = True

                reviews = []

                WebDriverWait(self.driver, 30).until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div[class="m6QErb"][jsan="t-dgE5uNmzjiE,7.m6QErb"] .jftiEf.L6Bbsd')))

                review_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, 'div[class="m6QErb"][jsan="t-dgE5uNmzjiE,7.m6QErb"] .jftiEf.L6Bbsd')

                for review in review_elements:
                    ActionChains(self.driver).move_to_element(
                        review).perform()

                    author = review.find_element(
                        By.CSS_SELECTOR, '.d4r55').text.strip()

                    stars = review.find_element(By.CSS_SELECTOR, '.kvMYJc').get_attribute(
                        'aria-label').strip().split('\xa0')[0]

                    more_button = review.find_elements(
                        By.CSS_SELECTOR, '.w8nwRe.kyuRq')
                    if len(more_button) > 0:
                        more_button[0].click()

                    text = review.find_element(
                        By.CSS_SELECTOR, '.wiI7pd').text.strip()

                    reviews.append({
                        'author': author,
                        'stars': stars,
                        'review': text
                    })

                self.data[f'reviews_{lang}'] = reviews

        except Exception as e:
            if self.verbose:
                print(f'reviews_{lang} not found')

        # finally:
        #     if changed_page:
        #         self.driver.back()
        #         self.wait_for_element(
        #             'div[class="onegoogle noprint app-sandbar-vasquette"]')

    def scrape(self, driver, place, lang, current_window_index=0):
        if place['googlePlaceId'] is None:
            return None

        main_windows_name = driver.window_handles[current_window_index]

        try:
            self.place = place
            self.lang = lang

            self.driver = driver

            # self.init_driver()

            self.driver.switch_to.new_window(WindowTypes.TAB)

            self.driver.set_page_load_timeout(60)
            self.driver.get(
                f"https://www.google.com/maps/place/?q=place_id:{place['googlePlaceId']}&hl={'en' if lang == 'en' else 'es-419'}")

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
                'telf': None,
                'email': None,
                'lat': None,
                'lon': None,
                'imagenes': [],
                'duration': None,
                'stars': None,
                'costos': [],
                'workingH': {},
                'reviews_en': [],
                'reviews_es': [],
                'categorias': []
            }

            if self.place['web'] is None:
                self.get_web()

            if self.place['stars'] is None:
                self.get_stars()

            if self.place['telf'] is None:
                self.get_telf()

            if self.place['workingH'] == {} and lang == 'es':
                self.get_workingH()

            if self.place['lat'] is None or self.place['lon'] is None:
                self.get_coordenadas()

            if self.place['duration'] is None:
                self.get_duration(self.lang)

            if self.place['imagenes'] == []:
                self.get_imagenes()

            if self.place['categorias'] == []:
                self.get_categorias()

            self.get_descripcion(self.lang)
            self.get_direccion(self.lang)

            self.get_reviews(self.lang)

            if self.driver is not None:
                try:
                    self.driver.backend.storage.clear_requests()
                except:
                    pass
                self.driver.close()
                self.driver.switch_to.window(window_name=main_windows_name)

            return self.data

        except Exception as e:
            if self.verbose:
                print(f'Error scraping {place["_id"]}')
                print(e)
                traceback.print_exc()

            if self.driver is not None:
                try:
                    self.driver.backend.storage.clear_requests()
                except:
                    pass
                self.driver.close()
                self.driver.switch_to.window(window_name=main_windows_name)

            return None
