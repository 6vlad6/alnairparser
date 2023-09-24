import requests
import json
import re


BASE_URL = "https://api.alnair.ae/v1/rc/search?page={}&limit=30&mapBounds%5Beast%5D=55.403366088867195&mapBounds%5Bnorth%5D=25.401724200763503&mapBounds%5Bsouth%5D=24.906990021902633&mapBounds%5Bwest%5D=55.11909484863282&isList=1&isPin=1"
APARTMENTS_URL = "https://api.alnair.ae/v1/rc/view/{}"
VILLA_URL = "https://api.alnair.ae/v1/village/view/{}"
INFO_URL = "https://api.alnair.ae/v1/info"

class Parser:
    def __init__(self, url_projects, url_rc, url_village, url_info):
        """
        Инициализация класса
        :param url_projects: шаблон url для сбора проектов
        :param url_rc: шаблон url страницы квартиры
        :param url_village: шаблон url страницы виллы
        """

        self.url_projects = url_projects
        self.url_rc = url_rc
        self.url_village = url_village
        self.url_info = url_info

    def remove_html_tags(self, text):
        """
        Убрать html-теги из текста
        :param text: текст для обработки
        :return: обработанный текст
        """

        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)


    def get_additional_info(self):
        """
        Собрать словарь-справочник с расшифровкой преимуществ квартиры/виллы
        :return: словарь {advantage_id: 'advantage'}
        """

        r = requests.get(self.url_info)
        info_data = json.loads(r.text)['data']['catalogs']

        info = info_data['residential_complex_advantages']['items'] + info_data['village_advantages']['items'] + \
               info_data['village_apartment_advantages']['items']

        info_dict = {item['id']: item['value'] for item in info}

        return info_dict

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
        :param project: вводные данные проекты - id, type
        :return: словарь информации
        """

        info_dict = self.get_additional_info()  # получение словаря доп информации по объекту
        try:
            project_dict = {}
            r = requests.get(self.url_rc.format(project[0]))
            project_data = json.loads(r.text)

            description = ''
            try:
                description = self.remove_html_tags(project_data['description'])
            except:
                pass

            address = ''
            try:
                address = project_data['address']
            except:
                pass

            predicted_completion_date = ''
            try:
                predicted_completion_date = project_data['predicted_completion_at'].split()[0]
            except:
                pass

            developer = ''
            try:
                developer = project_data['developer']['title']
            except:
                pass

            photos = []
            try:
                photos_arr = project_data['presentation']

                for elem in photos_arr:
                    photos.append(elem['url'])
            except:
                pass

            if project[1] == "rc":
                project_type = 'apartments'

                floors = ''
                try:
                    floors = project_data['stats']['total']['unitsMaxFloor']
                except:
                    pass

                advantages = []
                try:
                    advantages_ids = project_data['catalogs']['residential_complex_advantages']

                    for advantage in advantages_ids:
                        advantages.append(info_dict[advantage])
                except:
                    pass

                project_dict = {
                    'type': project_type,
                    'description': description,
                    'address': address,
                    'predicted_completion_date': predicted_completion_date,
                    'area': floors,
                    'developer': developer,
                    'advantages': advantages,
                    'photos': photos
                }

            elif project[1] == 'village':
                project_type = "villa"

                advantages = []
                try:
                    advantages_ids = project_data['catalogs']['village_advantages']

                    for advantage in advantages_ids:
                        advantages.append(info_dict[advantage])
                except:
                    pass

                cottages_data = []
                try:
                    cottages = project_data['stats']['cottages']
                    for cottage_type in cottages:
                        cottage_data = cottages[cottage_type]
                        cottages_data.append(
                            [cottage_data['squareMin'], cottage_data['sumMin'], cottage_data['sumMax']])
                except:
                    pass

                project_dict = {
                    'type': project_type,
                    'description': description,
                    'address': address,
                    'predicted_completion_date': predicted_completion_date,
                    'developer': developer,
                    'advantages': advantages,
                    'photos': photos,
                    'area': cottages_data
                }

            return project_dict

        except Exception as e:
            print(project[0], " - ", str(e))
            pass

    def get_projects_info(self):
        """
        Собрать информацию по всем проектам
        :return: массив
        """

        info_dict = self.get_additional_info()  # получение словаря доп информации по объекту
        projects = self.collect_projects()  # все объекты

        projects_res = []
        for project in projects:
            project_res = self.get_project_info(project)
            projects_res.append(project_res)

        return projects_res


parser = Parser(BASE_URL, APARTMENTS_URL, VILLA_URL, INFO_URL)
res = parser.get_projects_info()
print(res)