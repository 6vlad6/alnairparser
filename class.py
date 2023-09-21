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
            url = BASE_URL.format(page_num)
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

    def get_project_info(self):
        """
        Собрать информацию по проекту
        :return: массив
        """

        # получение словаря преимуществ объекта
        r = requests.get(self.url_info)
        info_data = json.loads(r.text)['data']['catalogs']
        info = info_data['residential_complex_advantages']['items'] + info_data['village_advantages']['items'] + info_data['village_apartment_advantages']['items']
        info_dict = {item['id']: item['value'] for item in info}


        projects = self.collect_projects()

        for project in projects:
            try:
                project_dict = {}
                r = requests.get(self.url_rc.format(project[0]))
                project_data = json.loads(r.text)

                description = self.remove_html_tags(project_data['description'])
                address = project_data['address']

                predicted_completion_date = None
                try:
                    predicted_completion_date = project_data['predicted_completion_at'].split()[0]
                except AttributeError:
                    pass

                developer = project_data['developer']['title']

                photos_arr = project_data['presentation']

                photos = []
                for elem in photos_arr:
                    photos.append(elem['url'])

                if project[1] == "rc":
                    project_type = 'apartments'
                    floors = project_data['stats']['total']['unitsMaxFloor']

                    advantages_ids = project_data['catalogs']['residential_complex_advantages']
                    advantages = []
                    for advantage in advantages_ids:
                        advantages.append(info_dict[advantage])

                    project_dict = {
                        'type': project_type,
                        'description': description,
                        'address': address,
                        'predicted_completion_date': predicted_completion_date,
                        'floors': floors,
                        'developer': developer,
                        'advantages': advantages,
                        'photos': photos
                    }

                elif project[1] == 'village':
                    project_type = "villa"
                    advantages_ids = project_data['catalogs']['village_advantages']
                    advantages = []
                    for advantage in advantages_ids:
                        advantages.append(info_dict[advantage])

                    project_dict = {
                        'type': project_type,
                        'description': description,
                        'address': address,
                        'predicted_completion_date': predicted_completion_date,
                        'developer': developer,
                        'advantages': advantages,
                        'photos': photos
                    }

                print(project_dict)
            except Exception as e:
                print(project[0], " - ", str(e))
                pass

        return 1


parser = Parser(BASE_URL, APARTMENTS_URL, VILLA_URL, INFO_URL)
res = parser.get_project_info()
print(res)