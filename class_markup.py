import requests
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from bs4 import BeautifulSoup


BASE_URL = "https://api.alnair.ae/v1/rc/search?page={}&limit=30&mapBounds%5Beast%5D=55.403366088867195&mapBounds%5Bnorth%5D=25.401724200763503&mapBounds%5Bsouth%5D=24.906990021902633&mapBounds%5Bwest%5D=55.11909484863282&isList=1&isPin=1"
APARTMENTS_URL = "https://alnair.ae/app/view/{}"
VILLAGE_URL = "https://alnair.ae/app/village/{}"
INFO_URL = "https://api.alnair.ae/v1/info"

class Parser:
    def __init__(self, url_projects, apartments_url, village_url, last_id):
        """
        Инициализация класса
        :param url_projects: шаблон url для сбора проектов
        :param apartments_url: url страницы квартиры
        :param village_url: url страницы виллы
        :param last_id: последний обработанный id
        """

        self.url_projects = url_projects
        self.apartments_url = apartments_url
        self.village_url = village_url
        self.last_id = last_id

    def create_driver(self, page_url):
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

    def remove_html_tags(self, text):
        """
        Убрать html-теги из текста
        :param text: текст для обработки
        :return: обработанный текст
        """

        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)

    def collect_projects(self):
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
            url = self.url_projects.format(page_num)
            r = requests.get(url)
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


    def get_project_info(self, project:list):
        """
        Собрать информацию по проекту
        :param project: вводные данные проекты - [id, type]
        :return: словарь информации
        """

        driver = None
        project_type = ''

        if project[1] == 'rc':
            driver = self.create_driver(self.apartments_url.format(project[0]))
            project_type = 'apartments'

        elif project[1] == 'village':
            driver = self.create_driver(self.village_url.format(project[0]))
            project_type = 'villa'

        project_dict = {}
        time.sleep(5)

        page_data = driver.find_element(By.CLASS_NAME, "ReactModalPortal")
        page_markup = page_data.get_attribute('innerHTML')
        page_soup = BeautifulSoup(page_markup, 'html.parser')

        room_blocks =  page_soup.find_all('div', class_='_root_16pwg_1')

        buildings = []

        for room_block in room_blocks:
            block_dict = {}
            try:
                room_block_title = room_block.find('div', class_="CssMediaQuery _hide_md_14ik7_74")
                room_title = room_block_title.find('div', '_mobileHeader_l3ze4_17').find('span').text
                block_dict[room_title] = {}

                total_units = room_block_title.find_all('span', class_="_root_8nc73_1 _sizeXS_8nc73_9")[0].text.split()[0]
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

                rooms = room_block.find('div', class_='swiper-wrapper').find_all('div',recursive=False)

                for room in rooms:
                    room_name = room.find('span', "_root_8nc73_1 _sizeM_8nc73_17 font-bold whitespace-break-spaces").text

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

        title = ''
        try:
            title_block = page_soup.find('header', "_header_p0mcl_10")
            title = title_block.find('div', 'LinesEllipsis').text
        except Exception as e:
            print(str(e))
            print(f"Can't find title in project {project[0]}. Check it's page")

        description = ''
        try:
            description = page_soup.find('div', "_truncateHtmlContent_1g4yz_5").text
            description = self.remove_html_tags(description)
        except Exception as e:
            print(str(e))
            print(f"Can't find description in project {project[0]}. Check it's page")

        address = ''
        try:
            address = page_soup.find('span', '_root_8nc73_1 _sizeM_8nc73_17 font-bold').text
        except Exception as e:
            print(str(e))
            print(f"Can't find address in project {project[0]}. Check it's page")

        predicted_completion_date = ''
        try:
            predicted_completion_date = page_soup.find('span', '_root_8nc73_1 _sizeM_8nc73_17 _color_blue_8nc73_126 font-bold').text.split()[0].replace("/", "-")
        except Exception as e:
            print(str(e))
            print(f"Can't find completion date in project {project[0]}. Check it's page")

        developer = {
            'name': '',
            'description': '',
            'link': ''
        }

        developer_name = ''
        try:
            developer_name = page_soup.find('div', class_='_root_1hm3d_1').find('span', class_='_root_8nc73_1 _sizeM_8nc73_17 font-bold').text
            developer['name'] = developer_name
        except Exception as e:
            print(str(e))
            print(f"Can't find developer name in project {project[0]}. Check it's page")

        developer_description = ''
        try:
            main_block = page_soup.find('main', "_main_194ew_118").find_all('div', recursive=False)[-1]
            developer_description = main_block.find('div', '_truncateHtmlContent_1g4yz_5 _is_hidden_1g4yz_42').text
            developer['description'] = developer_description
        except Exception as e:
            print(str(e))
            print(f"Can't find developer description in project {project[0]}. Check it's page")

        developer_link = ''
        try:
            main_block = page_soup.find('main', "_main_194ew_118").find_all('div', recursive=False)[-1]
            developer_link = main_block.find('a')['href']
            developer['link'] = developer_link
        except Exception as e:
            print(str(e))
            print(f"Can't find developer link in project {project[0]}. Check it's page")

        photos = []
        try:
            photos_arr = page_soup.find('div', class_='_sliderWrapper_1lbza_1').find_all('img')

            for elem in photos_arr:
                photos.append(elem['src'])
        except Exception as e:
            print(str(e))
            print(f"Can't find photos in project {project[0]}. Check it's page")

        brochure = ''
        try:
            brochure = page_soup.find('a', class_="_root_5e8ki_1")['href']
        except Exception as e:
            print(str(e))
            print(f"Can't find brochure in project {project[0]}. Check it's page")

        floors = ''
        try:
            floors = page_soup.find('section', "_root_wmc3k_1").find('span',
                                                                     '_root_8nc73_1 _sizeM_8nc73_17 font-bold').text
        except Exception as e:
            print(str(e))
            print(f"Can't find floors in project {project[0]}. Check it's page")

        advantages = []
        try:
            advantages_blocks = page_soup.find_all("div", "_item_lxv6i_14")
            for advantage in advantages_blocks:
                advantages.append(advantage.find('span', '_root_8nc73_1 _sizeS_8nc73_13 ml-2').text)
        except Exception as e:
            print(str(e))
            print(f"Can't find advantages in project {project[0]}. Check it's page")

        project_dict = {
            'id': project[0],
            'type': project_type,
            'title': title,
            'description': description,
            'address': address,
            'predicted_completion_date': predicted_completion_date,
            'floors': floors,
            'developer': developer,
            'advantages': advantages,
            'brochure': brochure,
            'photos': photos,
            'buildings': buildings
        }

        return project_dict

    def get_projects_info(self):
        """
        Собрать информацию по всем проектам
        :return: массив
        """
        projects = self.collect_projects()  # все объекты
        projects_res = []

        for project in projects:
            try:
                project_dict = self.get_project_info(project)

                projects_res.append(project_dict)

            except Exception as e:
                print(project[0], " - ", str(e))
                pass

        return projects_res

parser = Parser(BASE_URL, APARTMENTS_URL, VILLAGE_URL, 1554)
# res_array = parser.get_projects_info()
res_ordinary = parser.get_project_info([1577, 'rc'])
print(res_ordinary)