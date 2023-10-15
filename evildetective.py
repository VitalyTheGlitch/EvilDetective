import numpy as np
import cv2
import requests
import urllib
import vk_requests
import io
import json
import os
import sys
import random
import secrets
import time
import string
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from requests_futures.sessions import FuturesSession
from PIL import Image
from dotenv import dotenv_values
from datetime import datetime
from enum import Enum
from colorama import Fore, Back, Style, init

init()

config = dotenv_values('.env')

TOKEN = config['TOKEN']


def cprint(*args, color=Fore.RESET, mark='*', sep=' ', end='\n', frame_index=1, **kwargs):
    frame = sys._getframe(frame_index)

    colors = {
        'bgreen': Fore.GREEN + Style.BRIGHT,
        'bred': Fore.RED + Style.BRIGHT,
        'bblue': Fore.BLUE + Style.BRIGHT,
        'byellow': Fore.YELLOW + Style.BRIGHT,
        'green': Fore.GREEN,
        'red': Fore.RED,
        'blue': Fore.BLUE,
        'yellow': Fore.YELLOW,
        'bright': Style.BRIGHT,
        'srst': Style.NORMAL,
        'crst': Fore.RESET,
        'rst': Style.NORMAL + Fore.RESET
    }

    colors.update(frame.f_globals)
    colors.update(frame.f_locals)
    colors.update(kwargs)

    unfmt = ''

    if mark is not None:
        unfmt += f'{color}[{Style.BRIGHT}{mark}{Style.NORMAL}]{Fore.RESET}{sep}'

    unfmt += sep.join(args)

    fmted = unfmt

    for attempt in range(10):
        try:
            fmted = string.Formatter().vformat(unfmt, args, colors)

            break
        except KeyError as e:
            key = e.args[0]

            unfmt = unfmt.replace('{' + key + '}', '{{' + key + '}}')

    print(fmted, sep=sep, end=end)


def info(*args, sep=' ', end='\n', **kwargs):
    cprint(*args, color=Fore.GREEN, mark='*', sep=sep, end=end, frame_index=2, **kwargs)


def warn(*args, sep=' ', end='\n', **kwargs):
    cprint(*args, color=Fore.YELLOW, mark='!', sep=sep, end=end, frame_index=2, **kwargs)


def error(*args, sep=' ', end='\n', **kwargs):
    cprint(*args, color=Fore.RED, mark='!', sep=sep, end=end, frame_index=2, **kwargs)


def fail(*args, sep=' ', end='\n', **kwargs):
    cprint(*args, color=Fore.RED, mark='!', sep=sep, end=end, frame_index=2, **kwargs)

    exit(1)


def tally(*args, color=Fore.BLUE, mark='>>>', sep=' ', end='\n', **kwargs):
    cprint(color + f'{bright}{mark}{rst}', *args, mark=None, sep=sep, end=end, frame_index=2, **kwargs)


class QueryStatus(Enum):
    CLAIMED = 'Claimed'
    AVAILABLE = 'Available'
    UNKNOWN = 'Unknown'
    ILLEGAL = 'Illegal'

    def __str__(self):
        return self.value


class QueryResult:
    def __init__(self, username, site_name, site_url_user, status, query_time=None, context=None):
        self.username = username
        self.site_name = site_name
        self.site_url_user = site_url_user
        self.status = status
        self.query_time = query_time
        self.context = context

    def __str__(self):
        status = str(self.status)

        if self.context is not None:
            status += f' ({self.context})'

        return status


class SiteInformation:
    def __init__(self, name, url_home, url_username_format, username_claimed, information, username_unclaimed=secrets.token_urlsafe(10)):
        self.name = name
        self.url_home = url_home
        self.url_username_format = url_username_format
        self.username_claimed = username_claimed
        self.username_unclaimed = secrets.token_urlsafe(32)
        self.information = information

    def __str__(self):
        return f'{self.name} ({self.url_home})'


class SitesInformation:
    def __init__(self, data_file_path=None):
        if not data_file_path:
            data_file_path = 'https://raw.githubusercontent.com/sherlock-project/sherlock/master/sherlock/resources/data.json'

        if not data_file_path.lower().endswith('.json'):
            raise FileNotFoundError(f'Incorrect JSON file extension for data file {data_file_path}.')

        if data_file_path.lower().startswith('http'):
            try:
                response = requests.get(url=data_file_path)
            except Exception as error:
                raise FileNotFoundError(f'Problem while attempting to access data file URL {data_file_path}: {error}')

            if response.status_code != 200:
                raise FileNotFoundError(
                    f'Bad response while accessing '
                    f'data file URL {data_file_path}.'
                )
            try:
                site_data = response.json()
            except Exception as error:
                raise ValueError(f'Problem parsing json contents at {data_file_path}: {error}.')

        else:
            try:
                with open(data_file_path, 'r', encoding='utf-8') as file:
                    try:
                        site_data = json.load(file)
                    except Exception as error:
                        raise ValueError(f'Problem parsing json contents at {data_file_path}: {error}.')
            except FileNotFoundError:
                raise FileNotFoundError(f'Problem while attempting to access data file {data_file_path}.')

        self.sites = {}

        for site_name in site_data:
            try:
                self.sites[site_name] = SiteInformation(
                    site_name,
                    site_data[site_name]['urlMain'],
                    site_data[site_name]['url'],
                    site_data[site_name]['username_claimed'],
                    site_data[site_name]
                )
            except KeyError as error:
                raise ValueError(f'Problem parsing json contents at {data_file_path}: Missing attribute {error}.')

        return

    def site_name_list(self):
        return sorted([site.name for site in self], key=str.lower)

    def __iter__(self):
        for site_name in self.sites:
            yield self.sites[site_name]

    def __len__(self):
        return len(self.sites)


class EvilFuturesSession(FuturesSession):
    def request(self, method, url, hooks={}, *args, **kwargs):
        start = time.monotonic()

        def response_time(resp, *args, **kwargs):
            resp.elapsed = time.monotonic() - start

        try:
            if isinstance(hooks['response'], list):
                hooks['response'].insert(0, response_time)

            elif isinstance(hooks['response'], tuple):
                hooks['response'] = list(hooks['response'])
                hooks['response'].insert(0, response_time)

            else:
                hooks['response'] = [response_time, hooks['response']]
        except KeyError:
            hooks['response'] = [response_time]

        return super(EvilFuturesSession, self).request(method, url, hooks=hooks, *args, **kwargs)


def get_response(request_future, error_type, social_network):
    response = None
    error_context = 'General Unknown Error'
    exception_text = None

    try:
        response = request_future.result()

        if response.status_code:
            error_context = None
    except requests.exceptions.HTTPError as errh:
        error_context = 'HTTP Error'
        exception_text = str(errh)
    except requests.exceptions.ProxyError as errp:
        error_context = 'Proxy Error'
        exception_text = str(errp)
    except requests.exceptions.ConnectionError as errc:
        error_context = 'Error Connecting'
        exception_text = str(errc)
    except requests.exceptions.Timeout as errt:
        error_context = 'Timeout Error'
        exception_text = str(errt)
    except requests.exceptions.RequestException as err:
        error_context = 'Unknown Error'
        exception_text = str(err)

    return response, error_context, exception_text


def interpolate_string(object, username):
    if isinstance(object, str):
        return object.replace('{}', username)

    elif isinstance(object, dict):
        for key, value in object.items():
            object[key] = interpolate_string(value, username)

    elif isinstance(object, list):
        for i in object:
            object[i] = interpolate_string(object[i], username)

    return object


def usernames(username, site_data, proxy=None, timeout=60):
    underlying_session = requests.session()
    underlying_request = requests.Request()

    if len(site_data) >= 20:
        max_workers = 20

    else:
        max_workers = len(site_data)

    session = EvilFuturesSession(max_workers=max_workers, session=underlying_session)

    results_total = {}

    for social_network, net_info in site_data.items():
        results_site = {
            'url_main': net_info.get('urlMain')
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:55.0) Gecko/20100101 Firefox/55.0'
        }

        if 'headers' in net_info:
            headers.update(net_info['headers'])

        url = interpolate_string(net_info['url'], username)

        regex_check = net_info.get('regexCheck')

        if regex_check and re.search(regex_check, username) is None:
            results_site['status'] = QueryResult(username, social_network, url, QueryStatus.ILLEGAL)

            results_site['url_user'] = ''
            results_site['http_status'] = ''
            results_site['response_text'] = ''

        else:
            results_site['url_user'] = url
            url_probe = net_info.get('urlProbe')
            request_method = net_info.get('request_method')
            request_payload = net_info.get('request_payload')
            request = None

            if request_method is not None:
                if request_method == 'GET':
                    request = session.get

                elif request_method == 'HEAD':
                    request = session.head

                elif request_method == 'POST':
                    request = session.post

                elif request_method == 'PUT':
                    request = session.put

                else:
                    raise RuntimeError(f'Unsupported request_method for {url}')

            if request_payload is not None:
                request_payload = interpolate_string(request_payload, username)

            if url_probe is None:
                url_probe = url

            else:
                url_probe = interpolate_string(url_probe, username)

            if request is None:
                if net_info['errorType'] == 'status_code':
                    request = session.head

                else:
                    request = session.get

            if net_info['errorType'] == 'response_url':
                allow_redirects = False
            else:
                allow_redirects = True

            if proxy is not None:
                proxies = {
                    'http': proxy,
                    'https': proxy
                }

                future = request(
                    url=url_probe,
                    headers=headers,
                    proxies=proxies,
                    allow_redirects=allow_redirects,
                    timeout=timeout,
                    json=request_payload
                )

            else:
                future = request(
                    url=url_probe,
                    headers=headers,
                    allow_redirects=allow_redirects,
                    timeout=timeout,
                    json=request_payload
                )

            net_info['request_future'] = future

        results_total[social_network] = results_site

    for social_network, net_info in site_data.items():
        results_site = results_total.get(social_network)

        url = results_site.get('url_user')
        status = results_site.get('status')

        if status is not None:
            continue

        error_type = net_info['errorType']
        error_code = net_info.get('errorCode')

        future = net_info['request_future']

        r, error_text, exception_text = get_response(request_future=future, error_type=error_type, social_network=social_network)

        try:
            response_time = r.elapsed
        except AttributeError:
            response_time = None

        try:
            http_status = r.status_code
        except:
            http_status = '?'

        try:
            response_text = r.text.encode(r.encoding or 'UTF-8')
        except:
            response_text = ''

        query_status = QueryStatus.UNKNOWN
        error_context = None

        if error_text is not None:
            error_context = error_text

        elif error_type == 'message':
            error_flag = True
            errors = net_info.get('errorMsg')

            if isinstance(errors, str):
                if errors in r.text:
                    error_flag = False

            else:
                for error in errors:
                    if error in r.text:
                        error_flag = False

                        break

            if error_flag:
                query_status = QueryStatus.CLAIMED

            else:
                query_status = QueryStatus.AVAILABLE

        elif error_type == 'status_code':
            if error_code == r.status_code:
                query_status = QueryStatus.AVAILABLE

            elif not r.status_code >= 300 or r.status_code < 200:
                query_status = QueryStatus.CLAIMED

            else:
                query_status = QueryStatus.AVAILABLE

        elif error_type == 'response_url':
            if 200 <= r.status_code < 300:
                query_status = QueryStatus.CLAIMED

            else:
                query_status = QueryStatus.AVAILABLE

        else:
            raise ValueError(f'Unknown Error Type {error_type} for site {social_network}')

        result = QueryResult(
            username=username,
            site_name=social_network,
            site_url_user=url,
            status=query_status,
            query_time=response_time,
            context=error_context
        )

        results_site['status'] = result
        results_site['http_status'] = http_status
        results_site['response_text'] = response_text

        results_total[social_network] = results_site

    return results_total


class YandexImages:
    name = 'Yandex'
    url = 'https://yandex.com/images/search?url={}&rpt=imageview'

    def search_url(self, image_url):
        return self.url.format(urllib.parse.quote_plus(image_url))

    def process(self, driver):
        if not driver.find_element(By.ID, 'cbir-sites-title'):
            return []

        items = []

        cbir_sites = driver.find_elements(By.CLASS_NAME, 'CbirSites-Item')

        for cbir_site in cbir_sites:
            title = cbir_site.find_element(By.CLASS_NAME, 'CbirSites-ItemTitle').text
            image = cbir_site.find_element(By.CLASS_NAME, 'Thumb-Handle').value_of_css_property('background').split('"')[1]
            source = cbir_site.find_element(By.TAG_NAME, 'a').get_attribute('href')

            item = {
                'title': title,
                'image': image,
                'source': source
            }

            items.append(item)

        return items

    def search(self, image_url):
        options = Options()
        options.add_argument('--headless')

        service = Service(executable_path='driver/chromedriver.exe', log_path=os.devnull)

        driver = webdriver.Chrome(options=options, service=service)

        driver.get(self.search_url(image_url))

        time.sleep(2)

        result = self.process(driver)

        driver.close()

        return result


def get_profile_groups(profile_id):
    user_groups = api.groups.get(user_id=profile_id, extended=1, fields='activity')['items']

    groups = {}

    for group in user_groups:
        if 'activity' in group \
                and 'Этот материал' not in group['activity'] \
                and ':' not in group['activity'] \
                and group['activity'] != 'Открытая группа' \
                and group['activity'] != 'Закрытая группа' \
                and group['activity'] != 'Молодёжное движение':
            if group['activity'] == 'Другая музыка':
                group['activity'] = 'Музыка'

            elif group['activity'] == 'Музыкант':
                group['activity'] = 'Музыканты'

            elif group['activity'] == 'Блогер':
                group['activity'] = 'Блогеры'

            elif group['activity'] == 'Фан-клуб':
                group['activity'] = 'Фан-клубы'

            groups[group['name']] = group['activity']

    return groups


def get_profile_info(profile_id):
    profile_info = api.users.get(
        user_ids=profile_id,
        fields='bdate, screen_name, sex, last_seen, online, personal, photo_max_orig'
    )[0]

    platform = [
        'Мобильная версия сайта',
        'iPhone',
        'iPad',
        'Android',
        'Windows Phone',
        'Windows 10',
        'Сайт'
    ]

    political = [
        'Коммунистические',
        'Социалистические',
        'Умеренные',
        'Либеральные',
        'Консервативные',
        'Монархические',
        'Ультраконсервативные',
        'Индиффирентные',
        'Либертарианские'
    ]

    people_main = [
        'Ум и креативность',
        'Доброта и честность',
        'Красота и здоровье',
        'Власть и богатство',
        'Смелость и упорство',
        'Юмор и жизнелюбие'
    ]

    life_main = [
        'Семья и дети',
        'Карьера и деньги',
        'Развлечения и отдых',
        'Наука и исследования',
        'Саморазвитие',
        'Красота и искусство',
        'Слава и влияние'
    ]

    smoking = [
        'Резко негативное',
        'Негативное',
        'Компромиссное',
        'Нейтральное',
        'Положительное'
    ]

    alcohol = [
        'Резко негативное',
        'Негативное',
        'Компромиссное',
        'Нейтральное',
        'Положительное'
    ]

    processed_info = {
        'name': profile_info['first_name'] + ' ' + profile_info['last_name'],
        'bdate': profile_info.get('bdate'),
        'online': 'Online' if profile_info['online'] else 'Offline',
        'image': profile_info['photo_max_orig']
    }

    if profile_info['screen_name'][2:] != str(profile_id):
        processed_info['username'] = profile_info['screen_name']

    if 'bdate' in profile_info:
        bdate = profile_info['bdate'].split('.')

        for i in range(len(bdate[:2])):
            if int(bdate[i]) < 10:
                bdate[i] = '0' + bdate[i]

        bdate = '.'.join(bdate)

        processed_info['bdate'] = bdate

    if 'last_seen' in profile_info:
        processed_info['last_seen'] = datetime.fromtimestamp(profile_info['last_seen']['time']).strftime('%H:%M:%S %d.%m.%Y')
        processed_info['platform'] = platform[profile_info['last_seen']['platform'] - 1]

    if 'personal' in profile_info:
        if profile_info['personal'].get('political', 0):
            processed_info['political'] = political[profile_info['personal'].get('political') - 1]

        if profile_info['personal'].get('people_main', 0):
            processed_info['people_main'] = people_main[profile_info['personal'].get('people_main') - 1]

        if profile_info['personal'].get('life_main', 0):
            processed_info['life_main'] = life_main[profile_info['personal'].get('life_main') - 1]

        if profile_info['personal'].get('smoking', 0):
            processed_info['smoking'] = smoking[profile_info['personal'].get('smoking') - 1]

        if profile_info['personal'].get('alcohol', 0):
            processed_info['alcohol'] = alcohol[profile_info['personal'].get('alcohol') - 1]

    return processed_info


def vk_search(first_name, last_name, city, interests):
    matches = {}

    users = api.users.search(q=f'{first_name} {last_name}', count=100, city=city, has_photo=True, fields='verified')['items']

    users = list(filter(lambda u: not u['is_closed'] and not u['verified'], users))

    if not users:
        fail('No users found.')

    for user in users:
        matches[user['id']] = 0

        groups = get_profile_groups(user['id'])

        for group in groups:
            for interest in interests:
                if interest in group.lower().split(' ') or interest in groups[group].lower():
                    matches[user['id']] += 1

    best_user = max(matches, key=lambda m: matches[m])

    best_user_info = get_profile_info(best_user)

    return best_user_info


def username_search(username):
    sites = SitesInformation(os.path.join(os.path.dirname(__file__), 'resources/data.json'))

    site_data = {site.name: site.information for site in sites}

    results = usernames(username, site_data)

    return results


def contains_face(image_url):
    r = requests.get(image_url)

    image = r.content

    image = Image.open(io.BytesIO(image))

    image = np.asarray(image)

    cascade = cv2.CascadeClassifier('resources/lbpcascade_frontalface.xml')

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    return bool(faces)


def get_input():
    target = input('Target name: ')

    if len(target.rsplit()) == 2:
        first_name, last_name = target.rsplit()

        if not first_name.isalpha() or last_name and not last_name.isalpha():
            fail('Incorrect name.')

    else:
        fail('Incorrect name.')

    first_name, last_name = target.split(' ')

    first_name = first_name.capitalize()
    last_name = last_name.capitalize()

    city = input('Target city: ')

    if not city.isalpha() or len(city.split(' ')) > 2:
        fail('Invalid city.')

    cities = api.database.getCities(country_id=1, q=city)['items']

    if not cities:
        fail('Invalid city.')

    city = cities[0]['id']

    interests = input('Target interests (separated by comma): ')

    interests = list(map(lambda i: i.strip().lower(), interests.split(', ')))

    return first_name, last_name, city, interests


try:
    api = vk_requests.create_api(service_token=TOKEN, api_version='5.130')
except Exception as e:
    fail(str(e))

cprint('{bred}Evil Detective{rst}\n', mark=None)

first_name, last_name, city, interests = get_input()

vk_info = vk_search(first_name, last_name, city, interests)

yim = YandexImages()
image = yim.search(vk_info['image'])
