import httpx
import asyncio

import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By

import time
from bs4 import BeautifulSoup


BASE_URL = "https://api.alnair.ae/v1/rc/search?page={}&limit=30&mapBounds%5Beast%5D=55.403366088867195&mapBounds%5Bnorth%5D=25.401724200763503&mapBounds%5Bsouth%5D=24.906990021902633&mapBounds%5Bwest%5D=55.11909484863282&isList=1&isPin=1"
APARTMENTS_URL = "https://alnair.ae/app/view/{}"
VILLAGE_URL = "https://alnair.ae/app/village/{}"

APARTMENTS_URL_API = 'https://api.alnair.ae/v1/rc/view/{}'
VILLAGE_URL_API = 'https://api.alnair.ae/v1/village/view/{}'
INFO_URL_API = "https://api.alnair.ae/v1/info"


class Parser:
    def __init__(self, url_projects, apartments_url, village_url, aparments_url_api, village_url_api, info_url_api, last_id):
        """
        Инициализация класса
        :param url_projects: шаблон url для сбора проектов
        :param apartments_url: url страницы квартиры
        :param village_url: url страницы виллы
        :param aparments_url_api: api эндпоинт квартиры
        :param village_url_api: api эндпоинт виллы
        :param info_url_api: api эндпоинт доп информации
        :param last_id: последний обработанный проект
        """

        self.url_projects = url_projects
        self.apartments_url = apartments_url
        self.village_url = village_url

        self.apartments_url_api = aparments_url_api
        self.village_url_api = village_url_api
        self.info_url_api = info_url_api

        self.last_id = last_id

    async def create_driver(self, page_url):
        """
        Функция создает драйвер для парсинга
        :param page_url: адрес страницы
        :return: драйвер
        """

        options = webdriver.ChromeOptions()
        options.add_argument("start-maximized")
        options.add_argument("--headless")  # работа без открытия браузера
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/105.0.0.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")

        driver = webdriver.Chrome(options=options)
        driver.maximize_window()

        driver.get(page_url)

        return driver

    async def remove_html_tags(self, text):
        """
        Убрать html-теги из текста
        :param text: текст для обработки
        :return: обработанный текст
        """

        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)

    async def get_additional_info(self):
        """
        Собрать словарь-справочник с расшифровкой преимуществ квартиры/виллы
        :return: словарь {advantage_id: 'advantage'}
        """

        async with httpx.AsyncClient(http2=True) as client:
            r = await client.get(self.info_url_api)

            info_data = json.loads(r.text)['data']['catalogs']

            info = info_data['residential_complex_advantages']['items'] + info_data['village_advantages']['items'] + \
                   info_data['village_apartment_advantages']['items']

            info_dict = {item['id']: item['value'] for item in info}

            return info_dict

    async def collect_projects(self):
        """
        Собрать массив всех проектов
        :return: массив id и type проектов
        """

        projects = []  # финальный массив id проектов
        prev_projects = None  # предыдущий массив
        page_num = 1

        # начиная со 2 страницы, проверяем полученный массив на новой странице с полученным массивом на старой странице
        # если равны - значит дошли до последней страницы
        while True:
            async with httpx.AsyncClient(http2=True) as client:
                url = self.url_projects.format(page_num)
                r = await client.get(url)
                projects_data = json.loads(r.text)['data']['list']

                new_projects = []
                for project in projects_data:
                    if project['id'] > self.last_id:
                        new_projects.append([project['id'], project['type']])

                if prev_projects == new_projects:
                    break
                projects.extend(new_projects)

                prev_projects = new_projects
                page_num += 1

        return projects

    async def get_project_info(self, project:list):
        """
        Собрать информацию по проекту
        :param project: вводные данные проекты - [id, type]
        :return: словарь проекта
        """

        driver = None
        httpx_client = httpx.AsyncClient(http2=True)
        project_type = ''

        if project[1] == 'rc':
            driver = await self.create_driver(self.apartments_url.format(project[0]))
            project_type = 'apartments'

        elif project[1] == 'village':
            driver = await self.create_driver(self.village_url.format(project[0]))
            project_type = 'villa'

        project_dict = {}
        time.sleep(5)

        page_data = driver.find_element(By.CLASS_NAME, "ReactModalPortal")
        page_markup = page_data.get_attribute('innerHTML')
        page_soup = BeautifulSoup(page_markup, 'html.parser')

        room_blocks = page_soup.find_all('div', class_='_root_16pwg_1')

        buildings = []

        for room_block in room_blocks:
            block_dict = {}
            try:
                room_block_title = room_block.find('div', class_="CssMediaQuery _hide_md_14ik7_74")
                room_title = room_block_title.find('div', '_mobileHeader_l3ze4_17').find('span').text
                block_dict[room_title] = {}

                total_units = room_block_title.find_all('span', class_="_root_8nc73_1 _sizeXS_8nc73_9")[0].text.split()[
                    0]
                min_max_squares = room_block_title.find_all('span', class_="_root_8nc73_1 _sizeXS_8nc73_9")[1].text

                block_min_square = ''
                block_max_square = ''

                if "—" in min_max_squares:
                    parts = min_max_squares.split("—")
                    block_min_square = parts[0].split()[0]
                    block_max_square = parts[1].split()[0]

                block_price_min = room_block.find('span', '_root_8nc73_1 _sizeXS_8nc73_9 font-bold').text
                block_price_min = "".join(str(block_price_min).split()[1:-1])

                block_dict[room_title] = {
                    'units': total_units,
                    'area_min': block_min_square,
                    'area_max': block_max_square,
                    'price_min': block_price_min,
                    'objects': []
                }

                rooms = room_block.find('div', class_='swiper-wrapper').find_all('div', recursive=False)

                for room in rooms:
                    room_name = room.find('span',
                                          "_root_8nc73_1 _sizeM_8nc73_17 font-bold whitespace-break-spaces").text

                    room_data = room.find('span', "_root_8nc73_1 _sizeXS_8nc73_9").find('div')

                    room_bedrooms = room_data.find('span').text.split()[0]

                    room_units = ''
                    room_min_square = ''

                    if project[1] == 'rc':
                        room_units = room_data.find_all('div', class_='_point_1g59m_8')[0].next_sibling.split()[0]
                        room_min_square = room_data.find_all('div', class_='_point_1g59m_8')[1].next_sibling.split()[1]
                    elif project[1] == 'village':
                        room_units = room_data.find_all('div', class_='_point_1g59m_8')[1].next_sibling.split()[0]
                        room_min_square = room_data.find_all('div', class_='_point_1g59m_8')[2].next_sibling.split()[1]

                    price = room.find_all('span', class_="_root_8nc73_1 _sizeXS_8nc73_9 font-bold")[0].text
                    room_price_min = ''
                    room_price_max = ''

                    if "—" in price:
                        parts = price.split("—")
                        room_price_min = parts[0].split("AED")[0].replace(" ", "")
                        room_price_max = parts[1].split("AED")[0].replace(" ", "")
                    else:
                        room_price_min = price.split("AED")[0].replace(" ", "")

                    room_img = room.find('img', class_="_image_zy93a_12")['src']

                    if room_name:
                        block_dict[room_title]['objects'].append({
                            'name': room_name,
                            'area_min': room_min_square,
                            'price_min': room_price_min,
                            'price_max': room_price_max,
                            'image_link': room_img,
                            'units_available': room_units,
                            'bedrooms_count': room_bedrooms,
                        })
            except:
                pass

            buildings.append(block_dict)

        async with httpx_client as client:
            info_dict = await self.get_additional_info()

            resp = None

            if project[1] == 'rc':
                resp = await client.get(self.apartments_url_api.format(project[0]))
            elif project[1] == 'village':
                resp = await client.get(self.village_url_api.format(project[0]))

            project_data = json.loads(resp.text)

            title = ''
            try:
                title = project_data['title']
            except Exception as e:
                print(str(e))
                print(f"Can't find title in project {project[0]}. Check it's page")

            description = ''
            try:
                description = await self.remove_html_tags(project_data['description'])
            except Exception as e:
                print(str(e))
                print(f"Can't find description in project {project[0]}. Check it's page")

            address = ''
            try:
                address = project_data['address']
            except Exception as e:
                print(str(e))
                print(f"Can't find address in project {project[0]}. Check it's page")

            start_date = ''
            try:
                start_date = project_data['start_at'].split()[0]
            except Exception as e:
                print(str(e))
                print(f"Can't find start date in project {project[0]}. Check it's page")

            predicted_completion_date = ''
            try:
                predicted_completion_date = project_data['predicted_completion_at'].split()[0]
            except Exception as e:
                print(str(e))
                print(f"Can't find completion date in project {project[0]}. Check it's page")


            developer = {
                'title': '',
                'description': '',
                'site': ''
            }

            try:
                developer['title'] = project_data['developer']['title']
            except Exception as e:
                print(str(e))
                print(f"Can't find developer title in project {project[0]}. Check it's page")

            try:
                developer['description'] = project_data['developer']['description']
            except Exception as e:
                print(str(e))
                print(f"Can't find developer description in project {project[0]}. Check it's page")

            try:
                developer['site'] = project_data['developer']['site']
            except Exception as e:
                print(str(e))
                print(f"Can't find developer site in project {project[0]}. Check it's page")

            photos = []
            try:
                photos_arr = project_data['presentation']

                for elem in photos_arr:
                    photos.append(elem['url'])
            except Exception as e:
                print(str(e))
                print(f"Can't find photos in project {project[0]}. Check it's page")

            brochure = ''
            try:
                brochure = project_data['documents'][0]['url']
            except Exception as e:
                print(str(e))
                print(f"Can't find brochure in project {project[0]}. Check it's page")

            floors = ''
            try:
                floors = project_data['stats']['total']['unitsMaxFloor']
            except Exception as e:
                print(str(e))
                print(f"Can't find floors in project {project[0]}. Check it's page")

            advantages = []
            try:
                if project[1] == 'rc':
                    advantages_ids = project_data['catalogs']['residential_complex_advantages']

                    for advantage in advantages_ids:
                        advantages.append(info_dict[advantage])

                elif project[1] == 'village':
                    advantages_ids = project_data['catalogs']['village_advantages']

                    for advantage in advantages_ids:
                        advantages.append(info_dict[advantage])

            except Exception as e:
                print(str(e))
                print(f"Can't find advantages in project {project[0]}. Check it's page")

            project_dict = {
                'id': project[0],
                'type': project_type,
                'title': title,
                'description': description,
                'address': address,
                'start_date': start_date,
                'predicted_completion_date': predicted_completion_date,
                'floors': floors,
                'developer': developer,
                'advantages': advantages,
                'brochure': brochure,
                'photos': photos,
                'buildings': buildings
            }

            return project_dict

parser = Parser(BASE_URL, APARTMENTS_URL, VILLAGE_URL, APARTMENTS_URL_API, VILLAGE_URL_API, INFO_URL_API, 1554)
print(asyncio.run(parser.get_project_info([1555, 'rc'])))