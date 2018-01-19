import hmac
import hashlib
import base64
from xml.etree import ElementTree

import boto3
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AlexaTopSites(object):
    def __init__(
            self,
            aws_access_key_id=None,
            aws_secret_access_key=None
    ):
        # keep the text as a class variable so that it can be reused
        # in different ways
        self._top_sites_text = None

        # # check to see if AWS keys are defined in env vars and assign
        # if not aws_access_key_id and not aws_secret_access_key:
        #     assert os.environ['AWS_ACCESS_KEY_ID'] is not None
        #     assert os.environ['AWS_SECRET_ACCESS_KEY'] is not None
        #
        #     self._aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
        #     self._aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']
        # else:
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key

    def request_top_sites(self, count=100, start=1):
        # get the current time stamp
        timestamp = datetime.utcnow()
        timestamp = timestamp.replace(microsecond=0)
        # the AWS API doesn't quite fit the Python iso format
        timestamp = timestamp.isoformat() + '.000Z'

        # all the required params
        params = [
            ('AWSAccessKeyId', self._aws_access_key_id),
            ('Action', 'TopSites'),
            ('Count', count),
            ('CountryCode', 'us'),
            ('ResponseGroup', 'Country'),
            ('SignatureMethod', 'HmacSHA256'),
            ('SignatureVersion', '2'),
            ('Start', start),
            ('Timestamp', timestamp)
        ]
        url = 'ats.amazonaws.com'
        full_url = 'http://{}/'.format(url)
        url_method = 'GET'

        # create a request with all the params required for signature
        req = requests.Request(
            method=url_method,
            url=full_url,
            params=params
        )
        prep = req.prepare()

        # remove the initial /? from the generated URL
        params_str = prep.path_url[2:]
        logger.debug('params_str: %s', params_str)

        # create string of params needed for signature
        params_to_hash = '\n'.join([url_method, url, '/', params_str])

        logger.debug('params_to_hash: {}'.format(params_to_hash))

        secret_key = self._aws_secret_access_key

        # hash the signature
        dig = hmac.new(secret_key, msg=params_to_hash,
                       digestmod=hashlib.sha256).digest()

        # encode to base64
        signature = base64.b64encode(dig).decode()

        logger.debug('signature: {}'.format(signature))

        logger.debug('before append: %s', params)
        # add calculated signature to URL parameters
        params.append(('Signature', signature))
        # sort the params in canonical order
        params = sorted(params, key=lambda param: param[0])
        logger.debug('final params: %s', params)
        # reset the URL and parameters
        prep.prepare_url(full_url, params)

        logger.debug('Request before send: {}'.format(prep.path_url))

        # send the full request to AWS
        s = requests.Session()
        response = s.send(prep)

        logger.debug(response.text)
        logger.debug('After response: {}'.format(response.request.path_url))

        self._top_sites_text = response.text

    def save_to_s3(self, bucket, object_key, region='us-east-1'):
        """
        Saves the Alexa top sites result to an S3 bucket.

        Args:
            bucket (str): Name of the bucket to upload to in S3
            object_key (str): File name to save in S3 bucket
            region (str): AWS region the bucket is in
        """
        if self._top_sites_text is None:
            logger.error('No top site information found! Run request to'
                         ' Alexa Top Sites service first!')

        # create S3 resource
        s3 = boto3.resource('s3', region_name=region,
                            aws_access_key_id=self._aws_access_key_id,
                            aws_secret_access_key=self._aws_secret_access_key)
        s3_object = s3.Object(bucket, object_key)

        # put the text found from top site text
        s3_object.put(Body=self._top_sites_text)

    def load_from_s3(self, bucket, object_key, region='us-east-1'):
        """
        Load the Alexa top sites from result from S3 file.

        Args:
            bucket (str): Name of the bucket that has the file in S3.
            object_key (str): File name in bucket.
            region (str): AWS region the bucket is in.
        """
        # create S3 resource
        s3 = boto3.resource('s3', region_name=region,
                            aws_access_key_id=self._aws_access_key_id,
                            aws_secret_access_key=self._aws_secret_access_key)
        s3_object = s3.Object(bucket, object_key)

        # put the text found from top site text
        self._top_sites_text = s3_object.get()['Body'].read()

    def save_to_local_file(self, path):
        """
        Saves the Alexa top sites result to a local file.
        Args:
            path (str): Path to the local file location.
        """
        if self._top_sites_text is None:
            logger.error('No top site information found! Run request to'
                         ' Alexa Top Sites service first!')

        # open file for writing and dump in text
        with open(path, "w") as text_file:
            text_file.write(self._top_sites_text)

    def load_from_local_file(self, path):
        """
        Loads the Alexa top sites result from a local file.
        Args:
            path (str): Path to the local file location.
        """
        # open file for writing and dump in text
        with open(path, "r") as text_file:
            self._top_sites_text = text_file.read()

    def get_site_urls(self):
        """
        Gets the URLs of the sites found from the Top Sites query
        Returns:
            List of URLs from Top Site query document

        """
        logger.debug('Reading XML to get site list')
        xml = ElementTree.fromstring(self._top_sites_text)
        namespace_map = {'aws': 'http://ats.amazonaws.com/doc/2005-11-21'}
        url_list = xml.findall('.//aws:DataUrl', namespace_map)
        parsed_urls = [url.text for url in url_list]

        logger.debug('Parsed URLs: %s', parsed_urls)
        return parsed_urls
