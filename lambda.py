from __future__ import print_function

import json
import logging
import string

import bs4
import re


class Website(object):
    def __init__(self, url, content, headers):
        self._url = url,
        self._content = content,

        self._headers = self._filter_headers(headers)

        logging.debug('headers: %s', self._headers)

        self._name = self._find_title()

        self.words = self.split_words()

        self.word_count = {}

    def __repr__(self):
        # return '{title} - {content_length}[{header_size}]'.format(
        #     content_length=str(len(self._content)),
        #     title=self._name,
        #     header_size=str(len(self._headers))
        # )
        return self.name

    def _find_title(self):
        html = bs4.BeautifulSoup(str(self._content), "html.parser")
        if html.title:
            return html.title.text

        return str(self._url)

    def _filter_headers(self, headers):
        # we just care about the headers, not their value
        return headers.keys()

    def split_words(self):
        html = bs4.BeautifulSoup(str(self._content), "html.parser")
        data = html.findAll(text=True)

        def visible(element):
            if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
                return False
            elif re.match('<!--.*-->', str(element.encode('utf-8'))):
                return False
            return True

        result = filter(visible, data)

        stripped = []
        punc = re.compile('[%s]' % re.escape(string.punctuation))

        p = re.compile('\\s*(.*\\S)?\\s*')
        for orig in result:
            logging.debug('before replace: %s', orig)
            orig = orig.replace('\\n', '')
            orig = orig.replace('\\r', '')
            orig = orig.replace('\\t', '')
            orig = punc.sub('', orig)
            logging.debug('after replace: %s', orig)
            m = p.match(orig)
            formatted = m.group(1)
            if formatted:
                logging.debug('after format: %s', formatted)
                split = formatted.split(' ')
                stripped.extend(split)
        logging.debug('site text: %s', stripped)
        return stripped

    @property
    def content(self):
        return self._content

    @property
    def name(self):
        return self._name

    @property
    def headers(self):
        return self._headers

    @property
    def word_count_size(self):
        return len(self.word_count.keys())

    def calculate_word_count(self):
        word_count = {}
        for word in self.words:
            if word not in word_count:
                word_count[word] = 1
            else:
                word_count[word] += 1

        self.word_count = word_count


def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    # print('Making request to %s', url)
    # resp = requests.get('http://' + url)
    #
    # site = Website(
    #     url=resp.url,
    #     content=resp.text,
    #     headers=resp.headers
    # )