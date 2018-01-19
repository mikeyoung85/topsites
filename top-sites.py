#!/usr/bin/env python

# built in
from __future__ import division

import argparse
import cProfile
import logging
import os
import pstats
from datetime import datetime
from functools import wraps
import StringIO
import multiprocessing
import re

# external
import requests

# local imports
from objs.site import Website, mapreduce, map_function, \
    reduce_function, partition_data, MapReduceSite
from objs.top_sites import AlexaTopSites

logger = logging.getLogger(__name__)


def timed(f):
    """
    Decorator to do a simple time measure for the length of the method call.
    Args:
        f: Function to be timed.
    Returns:
        Prints out the time it takes to run
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        start = datetime.now()
        result = f(*args, **kwargs)
        elapsed = datetime.now() - start
        time_ms = int(elapsed.total_seconds() * 1000)  # milliseconds
        # TODO: should dump this somewhere more useful
        print "%s took %d ms to finish" % (f.__name__, time_ms)
        print "with args: %s kwargs: %s" % (args, kwargs)
        return result

    return wrapper


@timed
def fill_site_data(url):
    """
    Makes a request to the URL and then runs a map reduce method to
    count the words on the site and the number of times they appear.
    Args:
        url: HTTP URL to call and run analysis on.

    Returns:
        Website containing calculated values as well as the content of the
        response to the URL.
        None if there was an error reading the site.
    """
    try:
        site = MapReduceSite(url=url)
        site.request_homepage()
        # site.calculate_word_count()
        return site
    except requests.exceptions.ConnectionError as e:
        logger.exception('Could not connect!')
        return None
    except:
        logger.exception('Error connecting to site!')
        return None

@timed
def find_average_word_count(sites):
    """
    Find the average of the total word count for all the sites read.
    Args:
        sites (list Website): List of all the websites analyzed.

    Returns:
        (float): Average number of words per site.
    """
    total = 0
    for site in sites:
        total += site.word_count_size

    return total / len(sites)


@timed
def find_top_20_headers(sites):
    """
    Find the top 20 headers returned from the website requests and the
    percentage of sites that returned that header.
    Args:
        sites (list Website): List of websites that have their word counts
          analyzed.

    Returns:
        (dict): Dict where the key is the header and the value is the percentage
        of sites that returned the header. Only returns the first 20 sorted by
        their percentage value.
    """
    header_dict = {}

    for site in sites:
        for header in site.headers:
            if header not in header_dict:
                header_dict[header] = []
            header_dict[header].append(site.name)

    headers_with_percent = {}
    for header in header_dict:
        headers_with_percent[header] = (len(header_dict[header]) / len(
            sites)) * 100.0

    sorted_headers = sorted(headers_with_percent.items(), key=lambda x: x[1],
                            reverse=True)
    # logging.info('Headers with pct: %s', sorted_headers)
    return sorted_headers[:20]


@timed
def find_top_20_headers_map_reduce(sites, worker_count):
    """
    Find the top 20 headers returned from the website requests and the
    percentage of sites that returned that header. This method uses a
    map-reduce algorithm to count the headers.
    Args:
        sites (list Website): List of websites that have their word counts
          analyzed.
        worker_count (int): Number of sub processes to use to run map-reduce
          header count.

    Returns:
        (dict): Dict where the key is the header and the value is the percentage
        of sites that returned the header. Only returns the first 20 sorted by
        their percentage value.

    """
    all_headers = []
    for site in sites:
        all_headers.extend(site.headers)
    logging.debug('all headers: %s', all_headers)

    header_count = mapreduce(
        all_items=all_headers,
        worker_count=worker_count,
        partition_func=partition_data,
        reduce_func=reduce_function,
        map_func=map_function
    )

    logging.debug('header count: %s', header_count)

    headers_with_percent = {}
    for header in header_count:
        logging.debug('Header: %s', header)
        headers_with_percent[header] = (header_count[header] / len(
            sites)) * 100.0

    sorted_headers = sorted(headers_with_percent.items(), key=lambda x: x[1],
                            reverse=True)
    # logging.info('Headers with pct: %s', sorted_headers)
    return sorted_headers[:20]


def parse_s3_url(url):
    """Parses the given URL to extract S3 bucket name and key name. URL must
       match one of the following formats for S3 urls:
         * http(s)://bucket.s3.amazonaws.com/key
         * http(s)://bucket.s3-aws-region.amazonaws.com/key
         * http(s)://s3.amazonaws.com/bucket/key
         * http(s)://s3-aws-region.amazonaws.com/bucket/key
         * s3://bucket/key
    Args:
       url (str): the url to be parsed

    Returns:
       (str, str): tuple of (bucket name, key)
    """
    match = re.search('^https?://([^.]+).s3.amazonaws.com/(.*)', url)
    if match:
        return match.group(1), match.group(2)
    match = re.search('^https?://([^.]+).s3-[^.]+.amazonaws.com/(.*)', url)
    if match:
        return match.group(1), match.group(2)
    match = re.search('^https?://s3.amazonaws.com/([^\/]+)/(.*)', url)
    if match:
        return match.group(1), match.group(2)
    match = re.search('^https?://s3-[^.]+.amazonaws.com/([^\/]+)/(.*)', url)
    if match:
        return match.group(1), match.group(2)
    match = re.search('^s3://([^\/]+)/(.*)', url)
    if match:
        return match.group(1), match.group(2)
    return None, None


def main(
        aws_access_key_id=None,
        aws_secret_access_key=None,
        local_file_location=None,
        s3_file_location=None,
        worker_processes=1
):
    if not aws_access_key_id and not aws_secret_access_key:
        aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
        aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']

    top_sites = AlexaTopSites(
        aws_secret_access_key=aws_secret_access_key,
        aws_access_key_id=aws_access_key_id
    )

    # top_sites.request_top_sites()
    # print top_sites.get_site_urls()

    if local_file_location:
        top_sites.load_from_local_file(local_file_location)
    elif s3_file_location:
        # parse the S3 URL into a bucket and object key
        bucket, key = parse_s3_url(s3_file_location)
        top_sites.load_from_s3(bucket, key)
    else:
        top_sites.request_top_sites()

    sites = top_sites.get_site_urls()

    pool = multiprocessing.Pool(processes=worker_processes)
    results = [pool.apply_async(fill_site_data, args=(site,)) for site in sites]
    full_sites = [p.get() for p in results]

    # remove site with no return result
    full_sites = [site for site in full_sites if site is not None]

    # do separate calculation here
    for site in full_sites:
        site.calculate_word_count()

    average_word_count = find_average_word_count(full_sites)
    sorted_by_word_count = sorted(full_sites, key=lambda x: x.word_count_size,
                                  reverse=True)

    top_headers = find_top_20_headers_map_reduce(full_sites, worker_processes)

    logger.debug('Sorted by word count: %s', sorted_by_word_count)

    logging.info('Websites sorted by their word count')
    for index, site in enumerate(sorted_by_word_count):
        logging.info('Site: %s - Rank: %d', site.url, index + 1)

    logger.info('Average word count: %s', average_word_count)

    logger.debug('Top 20 headers: %s', top_headers)
    logging.info('Top 20 headers and the percentage of sites that returned '
                 'them')
    for header in top_headers:
        logging.info('Header: %s - Pct: %05.2f', header[0], header[1])


if __name__ == '__main__':
    # TODO: add proper log configuration
    logging.basicConfig(level=logging.INFO)
    # a lot of URL calls get hung up, set this to DEBUG to see them
    logging.getLogger("requests.packages.urllib3").setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser(
        description='Calculate word count and header count for Alexa top 100 '
                    'sites')

    parser.add_argument(
        '--access-key-id',
        dest='access_key_id',
        default=None,
        help='AWS access key ID to use for S3 and AWS Top Sites API calls'
    )
    parser.add_argument(
        '--secret-access-key',
        dest='secret_access_key',
        default=None,
        help='AWS secret access key to use for S3 and AWS Top Sites API calls'
    )

    parser.add_argument(
        '--local-file',
        dest='local_file_location',
        default=None,
        help='Location of the local file containing the top sites data'
    )

    parser.add_argument(
        '--s3-location',
        dest='s3_location',
        default=None,
        help='Location of the top sites data file in S3.'
    )

    parser.add_argument(
        '--worker-processes',
        dest='worker_count',
        default=4,
        type=int,
        help='Number of sub processes to use for requesting site home pages'
    )

    args = parser.parse_args()
    pr = cProfile.Profile()
    pr.enable()

    main(
        aws_access_key_id=args.access_key_id,
        aws_secret_access_key=args.secret_access_key,
        local_file_location=args.local_file_location,
        s3_file_location=args.s3_location,
        worker_processes=args.worker_count
    )

    pr.disable()
    s = StringIO.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats('get_site_urls')
    ps.print_stats('fill_site_data')
    ps.print_stats('calculate_word_count')
    ps.print_stats('find_average_word_count')
    ps.print_stats('find_top_20_headers_map_reduce')

    print(s.getvalue())
