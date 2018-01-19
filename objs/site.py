# internal
import logging
import string
import multiprocessing
import re

# external
import requests
import bs4
import boto3

logger = logging.getLogger(__name__)

DB_TABLE = 'alexa-site-data'


class Website(object):
    """
    Class to represent a website and it's content. This has methods to
    help facilitate word count and header analysis.
    """
    def __init__(self, url, content=None, headers=None):
        if isinstance(url, tuple):
            self._url = url[0]
        else:
            self._url = url

        # set the default name to the URL
        self._name = self._url

        self._words = []
        self._word_count = {}

        # if the content was passed in go ahead and
        # parse it for the site title
        # split up the words for analysis
        self._content = content
        if self._content:
            self._name = self._find_title()
            self._words = self.split_words()

        # no headers were passed in set default to empty list
        if headers is None:
            headers = []
        self._headers = headers

    def __repr__(self):
        return self.url

    def request_homepage(self):
        """
        Makes a request to the website's homepage and sets up response
        for further analysis
        """
        try:
            logger.info('Making request to %s', self._url)
            resp = requests.get('http://' + self._url, timeout=1)

            # ignore any undecodable chars
            self._content = resp.text.encode('utf-8').decode('ascii', 'ignore')
            self._headers = self._filter_headers(resp.headers)
            logger.debug('headers: %s', self._headers)

            # fill out site data with the returned content
            self._name = self._find_title()
            self._words = self.split_words()
        except Exception as e:
            # many different exceptions have been encountered running requests
            # to the sites in the list
            logging.exception('Could not read %s homepage', self.url)

    def _find_title(self):
        """
        Tries to get the title from the website to use as the name. If one
        is not found, the URL is used as the name.
        """
        html = bs4.BeautifulSoup(str(self.content), "html.parser")
        if html.title:
            return html.title.text

        return str(self.url)

    def _filter_headers(self, headers):
        """
        Filters the header map into just the header keys
        since that is all we care about.
        Args:
            headers: Header map from a web response to the site.
        Returns:
            All header keys from response.

        """
        # we just care about the headers, not their value
        return headers.keys()

    def split_words(self):
        """
        Creates a list of all the visible words found from the site's
        homepage content. This will attempt to remove any non-visible
        HTML tags and special characters like new-line and tab chars.

        Returns:
            List of the visible words found after removing non-visible elements.
        """
        # TODO: figure out more efficient way to do this
        # TODO: could break this up in parts to split up work
        # parse the HTML
        html = bs4.BeautifulSoup(str(self._content), "html.parser")
        data = html.findAll(text=True)
        # logging.info('visible: %s', html)
        # data = html.get_text()

        # small method to determine if a tag is visible
        # TODO: may be a library that can do this better
        def visible(element):
            # known tags that would not be visible to a user
            if element.parent.name in [
                'style',
                'script',
                '[document]',
                'head',
                'title'
            ]:
                return False
            # remove any commented out code
            elif re.match('<!--.*-->', str(element.encode('utf-8'))):
                return False
            return True

        # filter out non-visible content from the data
        result = filter(visible, data)

        stripped = []
        # create regex to try and remove all punctuation to help
        # normalize word data
        punc = re.compile('[%s]' % re.escape(string.punctuation))

        p = re.compile('\\s*(.*\\S)?\\s*')
        for orig in result:
            # go through each word and try and remove special chars
            logger.debug('before replace: %s', orig)
            orig = orig.replace('\\n', '')
            orig = orig.replace('\\r', '')
            orig = orig.replace('\\t', '')
            orig = punc.sub('', orig)
            logger.debug('after replace: %s', orig)
            m = p.match(orig)
            formatted = m.group(1)
            if formatted:
                logger.debug('after format: %s', formatted)
                # split up all the words found after filter by whitespace
                split = formatted.split(' ')
                # add them to the results list
                stripped.extend(split)

        logger.debug('site text: %s', stripped)
        return stripped

    # property getters for external use
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
    def url(self):
        return self._url

    @property
    def word_count_size(self):
        return len(self.word_count.keys())

    @property
    def word_count(self):
        return self._word_count

    @property
    def word_list(self):
        return self._words

    def calculate_word_count(self):
        """
        A simple word count method to find how many times a word occurs
        in the site's homepage content.
        """
        word_count = {}
        for word in self.word_list:
            if word not in word_count:
                word_count[word] = 1
            else:
                word_count[word] += 1

        self._word_count = word_count

    def persist_to_db(self):
        """
        Persists this site's data to a DynamoDB table
        """
        # TODO: reconsider all of this
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table(DB_TABLE)
        logger.debug('word count size: %s', self.word_count_size)

        table.put_item(
            Item={
                "url": self.url,
                "content": self.content,
                "headers": self.headers,
                "word_count": self.word_count,
                "word_list": self.word_list,
                "word_count_size": self.word_count_size
            }
        )

    def get_from_db(self):
        """
        Retrieves site from the database with the matching URL.
        """
        # TODO: reconsider all of this
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.Table(DB_TABLE)
        logger.debug('word count size: %s', self.word_count_size)

        db_obj = table.get_item(
            Key={
                "url": self.url,
            }
        )['Item']

        self._content = db_obj.get('content', '')
        self._headers = db_obj.get('headers', [])
        self._word_count = db_obj.get('word_count', {})
        self._words = db_obj.get('word_list', [])


class MapReduceSite(Website):
    """
    Class to represent a website and it's content. This class uses map
    reduce to calculate the word count.
    """
    def __init__(self, worker_processes=4, *args, **kwargs):
        super(MapReduceSite, self).__init__(*args, **kwargs)
        self.workers = worker_processes

    def calculate_word_count(self):
        """
        Creates a word count map based on the content of the web site.
        """
        self._word_count = mapreduce(
            all_items=self._words,
            partition_func=partition_data,
            map_func=map_function,
            reduce_func=reduce_function,
            worker_count=self.workers
        )


def partition_data(items, workers):
    """
    Cuts data in parts. This parts is the data that will receive each of
    the workers.
    Args:
        items: Items to do work on.
        workers: Number of workers to use.
    """
    # Get the number of items for each process
    number_per_worker = int(len(items) / workers)

    # Create a list with lists
    for i in range(workers + 1):
        # use yield for range generator
        # split these items up in groups over the number of workers
        # example i = 1 and per_worker = 4
        # return items items[4:8]
        yield (items[i * number_per_worker:(i + 1) * (number_per_worker)])

    # Add remainder group if it doesn't divide nicely
    remainder_group = items[(i + 1) * number_per_worker:]
    if remainder_group:
        yield (remainder_group)


def map_function(words):
    """
    Maps the words and counts their occurrence
    Args:
        words: Words to analyze
    Returns:
        dict with the word as the key and the
          count as the value
    """
    # keep results of word count
    result = {}
    for word in words:
        if word not in result:
            result[word] = 1
        else:
            result[word] += 1
    return result


def reduce_function(word_maps):
    """
    Combine the data from the separate results together and
      reduce them to one map.

    Args:
        word_maps: All the results of the separate word counts.

    Returns:
        dict with the word as the key and the
          count as the value

    """
    # Reduce all the data by combining all the parts that are received
    result = {}
    for i in word_maps:
        for k, v in i.items():
            try:
                # result exists, add the value
                result[k] += v
            except KeyError:
                # new result, set the value
                result[k] = v
    return result


def mapreduce(
        all_items,
        worker_count,
        partition_func,
        map_func,
        reduce_func
):
    """
    The starting point for the map reduce process.
    Args:
        all_items: The list of all the items to analyze.
        worker_count: The number of worker processes to use
        partition_func: The function to use to partition the data equally.
            Arguments passed in are the total list of items, and the number
            of worker processes.
        map_func: Function to map the data to key/value map.
        reduce_func: Function to reduce all the partitioned data
            into one final key/value map.
    Returns:
        The final key/value map.
    """
    # Group the items for each worker
    group_items = list(partition_func(all_items, worker_count))

    # Call the map functions concurrently with a pool of processes
    pool = multiprocessing.Pool(processes=worker_count)
    sub_map_result = pool.map(map_func, group_items)

    # Reduce all the data captured
    return reduce_func(sub_map_result)
