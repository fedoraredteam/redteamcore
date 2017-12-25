import re
import os
import zlib
import gzip
import json
import tempfile
import requests

from frtcore import HTTP_CONNECTOR
from frtcore import FILE_CONNECTOR
from frtcore import DIRECTORY_CONNECTOR

class ResourceConnectorFactory(object):

    def __init__(self):
        pass

    @classmethod
    def location_is_url(cls, location):
        url_regex = re.compile(r'^(?:http|ftp)s?://' # http:// or https://
                               r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
                               r'localhost|' #localhost...
                               r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
                               r'(?::\d+)?' # optional port
                               r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if url_regex.match(location):
            return True
        return False

    @classmethod
    def create_connector(cls, location, **kwargs):
        if ResourceConnectorFactory.location_is_url(location):
            return HttpResourceConnector(location, **kwargs)
        elif os.path.isdir(location):
            return DirectoryResourceConnector(location, **kwargs)
        elif os.path.isfile(location):
            return FileResourceConnector(location, **kwargs)

class HttpResourceConnector(object):
    def __init__(self, location, **kwargs):
        self.location = location
        self.type = HTTP_CONNECTOR
        try:
            self.tlsverify = kwargs['tlsverify']
        except KeyError:
            self.tlsverify = True

    def open(self):
        data = None
        response = requests.get(self.location, verify=self.tlsverify, stream=True)
        response.raise_for_status()
        if 'json' in response.headers.get('content-type') or 'text' in response.headers.get('content-type'):
            data = response.content
        elif 'gzip' in response.headers.get('content-type'):
            data = HttpResourceConnector._decode_compressed_content(response)
        #TODO: Maybe parse before returning?  One day?
        elif 'xml' in response.headers.get('content-type'):
            data = response.content
        return data

    def exists(self):
        response = requests.get(self.location, verify=self.tlsverify, stream=True)
        if response.status_code >= 299:
            return False
        return True

    def delete(self):
        pass

    @classmethod
    def _decode_compressed_content(cls, response):
        if isinstance(response, str):
            return zlib.decompress(response, zlib.MAX_WBITS|32)
        return zlib.decompress(response.content, zlib.MAX_WBITS|32)

class FileResourceConnector(object):
    def __init__(self, location, **kwargs):
        self.location = location
        self.type = FILE_CONNECTOR

    def open(self):
        file_content = ''
        if self.location.endswith(".gz"):
            with gzip.open(self.location, 'rb') as gzip_file_obj:
                file_content = gzip_file_obj.read()
        else:
            with open(self.location, 'r') as file_obj:
                file_content = file_obj.read()
        return file_content

    def write(self, file_content):
        _, file_extension = os.path.splitext(self.location)
        if file_extension == '.gzip' or file_extension == '.gz':
            with gzip.open(self.location, 'wb') as gzip_file_obj:
                gzip_file_obj.write(json.dumps(file_content))
        elif file_extension == '.json':
            with open(self.location, "w") as json_file_obj:
                json.dump(file_content, json_file_obj)
        else:
            with open(self.location, "w") as file_obj:
                file_obj.write(file_content)

    def exists(self):
        return os.path.isfile(self.location)

    def delete(self):
        os.remove(self.location)

class DirectoryResourceConnector(object):

    def __init__(self, location, **kwargs):
        self.location = location
        self.type = DIRECTORY_CONNECTOR

    def open(self):
        filenames = [os.path.join(d, x)
                     for d, _, files in os.walk(self.location)
                     for x in files]
        return filenames

    def exists(self):
        return os.path.isdir(self.location)

    def delete(self):
        os.remove(self.location)
