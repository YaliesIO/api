from .source import Source
from .directory import Directory

from .s3 import ImageUploader

from bs4 import BeautifulSoup
import json
import requests
import os
import re
from cryptography.fernet import Fernet

# Image processing
from PIL import Image
from io import BytesIO


with open('app/scraper/res/majors.txt') as f:
    MAJORS = f.read().splitlines()
with open('app/scraper/res/major_full_names.json') as f:
    MAJOR_FULL_NAMES = json.load(f)


class FaceBook(Source):
    FERNET_KEY = os.environ.get('FERNET_KEY')

    def __init__(self, cookie, directory):
        self.cookie = cookie
        self.image_uploader = ImageUploader()
        self.fernet = Fernet(self.FERNET_KEY)

    ##########
    # Scraping
    ##########

    RE_ROOM = re.compile(r'^([A-Z]+)-([A-Z]+)(\d+)(\d)([A-Z]+)?$')
    RE_BIRTHDAY = re.compile(r'^[A-Z][a-z]{2} \d{1,2}$')
    RE_ACCESS_CODE = re.compile(r'[0-9]-[0-9]+')
    RE_PHONE = re.compile(r'[0-9]{3}-[0-9]{3}-[0-9]{4}')

    def get_html(self, cookie):
        filename = 'page.html'
        if not os.path.exists(filename):
            print('Page not cached, fetching.')
            requests.get('https://students.yale.edu/facebook/ChangeCollege',
                         params={
                             'newOrg': 'Yale College'
                         },
                         headers={
                             'Cookie': cookie,
                         })
            r = requests.get('https://students.yale.edu/facebook/PhotoPageNew',
                             params={
                                 'currentIndex': -1,
                                 'numberToGet': -1,
                             },
                             headers={
                                 'Cookie': cookie,
                             })
            html = r.text
            with open(filename, 'w') as f:
                f.write(html)
            print('Done fetching page.')
        else:
            print('Using cached page.')
            with open(filename, 'r') as f:
                html = f.read()
        return html

    def get_tree(self, html):
        print('Building tree.')
        tree = BeautifulSoup(html, 'html.parser')
        print('Done building tree.')
        return tree

    def get_containers(self, tree):
        return tree.find_all('div', {'class': 'student_container'})

    def clean_image_id(self, image_src):
        image_id = image_src.lstrip('/facebook/Photo?id=')
        # Check if image is not found
        if image_id == 0:
            return None
        return int(image_id)

    def clean_name(self, name):
        print('Parsing ' + name)
        first_name, last_name = name.strip().split(', ', 1)
        return first_name, last_name

    def clean_year(self, year):
        year = year.lstrip('\'')
        if not year:
            return None
        return 2000 + int(year)

    def compare_years(self, page_key, people, emails):
        print(f'Comparing years from {page_key} store.')
        with open(f'app/scraper/res/{page_key}.html.fernet', 'rb') as f:
            html = self.fernet.decrypt(f.read())
        tree = self.get_tree(html)
        containers = self.get_containers(tree)

        for container in containers:
            year = self.clean_year(container.find('div', {'class': 'student_year'}).text)
            info = container.find_all('div', {'class': 'student_info'})
            try:
                email = info[1].find('a').text
            except AttributeError:
                continue
            if email in emails and not people[emails[email]].get('leave') and email in emails and year is not None and people[emails[email]]['year'] is not None:
                people[emails[email]]['leave'] = (year < people[emails[email]]['year'])
                print(email + ' is' + (' not' if not people[emails[email]]['leave'] else '') + ' taking a leave.')
        return people

    def scrape(self):
        html = self.get_html(self.cookie)
        tree = self.get_tree(html)
        containers = self.get_containers(tree)

        if len(containers) == 0:
            print('No people were found on this page. There may be something wrong with authentication, aborting.')
            return []

        watermark_mask = Image.open('app/scraper/res/watermark_mask.png')
        print('Already hosting {} images.'.format(len(self.image_uploader.files)))

        people = []
        emails = {}
        for container in containers:
            person = {
                'school': 'Yale College',
                'school_code': 'YC',
            }

            person['last_name'], person['first_name'] = self.clean_name(container.find('h5', {'class': 'yalehead'}).text)
            person['year'] = self.clean_year(container.find('div', {'class': 'student_year'}).text)
            pronoun = container.find('div', {'class': 'student_info_pronoun'}).text
            person['pronoun'] = pronoun if pronoun else None

            info = container.find_all('div', {'class': 'student_info'})

            person['college'] = info[0].text.replace(' College', '')
            try:
                person['email'] = info[1].find('a').text
            except AttributeError:
                pass
            trivia = info[1].find_all(text=True, recursive=False)
            try:
                room = trivia.pop(0) if self.RE_ROOM.match(trivia[0]) else None
                if room:
                    person['residence'] = room
                    result = RE_ROOM.search(room)
                    person['building_code'], person['entryway'], person['floor'], person['suite'], person['room'] = result.groups()
                person['birthday'] = trivia.pop() if self.RE_BIRTHDAY.match(trivia[-1]) else None
                person['major'] = trivia.pop() if trivia[-1] in MAJORS else None
                if person['major'] and person['major'] in MAJOR_FULL_NAMES:
                    person['major'] = MAJOR_FULL_NAMES[person['major']]
            except IndexError:
                pass

            new_trivia = []
            for r in range(len(trivia)):
                row = trivia[r].strip()
                if row.endswith(' /'):
                    row = row.rstrip(' /')
                    if self.RE_ACCESS_CODE.match(row):
                        person['access_code'] = row
                    if self.RE_PHONE.match(row):
                        person['phone'] = self.clean_phone(row)
                    if len(new_trivia) == 1 and not person.get('residence'):
                        person['residence'] = new_trivia.pop(0)
                else:
                    new_trivia.append(row)
            trivia = new_trivia

            # Handle first row of address being duplicated for residence
            if len(trivia) >= 2 and trivia[0] == trivia[1] and not person.get('residence'):
                person['residence'] = trivia.pop(0)

            person['address'] = '\n'.join(trivia)

            person['leave'] = False
            person['eli_whitney'] = False

            image_id = clean_image_id(container.find('img')['src'])
            if image_id:
                image_filename = image_uploader.get_image_filename(image_id, person)
                if image_filename in image_uploader.files:
                    person['image'] = image_uploader.get_file_url(image_filename)
                else:
                    print('Image has not been processed yet.')
                    image_r = requests.get('https://students.yale.edu/facebook/Photo?id=' + str(image_id),
                                           headers={'Cookie': self.cookie},
                                           stream=True)
                    image_r.raw.decode_content = True
                    try:
                        im = Image.open(image_r.raw)

                        # Paste mask over watermark
                        im.paste(watermark_mask, (0, 0), watermark_mask)

                        output = BytesIO()
                        im.save(output, format='JPEG', mode='RGB')

                        person['image'] = self.image_uploader.upload_image(output, image_filename)
                    except OSError:
                        # "Cannot identify image" error
                        print('PIL could not identify image.')

            if person.get('email'):
                emails[person['email']] = len(people)
            people.append(person)

        # Check leaves
        people = compare_years('pre2020', people, emails)
        people = compare_years('fall2020', people, emails)

        return people

    def merge(self, current_people, new_people):
        # There shouldn't be any people yet, as this is the first source
        # So just concatenate the lists
        return current_people + new_people