import urllib.request
from urllib.error import HTTPError
try:
    urllib.request.urlopen('http://127.0.0.1:8000/api/locations')
except HTTPError as e:
    print(e.read().decode('utf-8'))
