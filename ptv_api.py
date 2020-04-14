from hashlib import sha1
import hmac
import binascii
import requests

def calculate_signature(url, key):
    hashed = hmac.new(str.encode(key), str.encode(url), sha1)
    signature = hashed.hexdigest()
    return signature

def get_url(url, dev_id, key):
    url += ('&' if ('?' in url) else '?')
    url += 'devid={}'.format(str(dev_id))

    signature = calculate_signature(url, key)

    return 'https://timetableapi.ptv.vic.gov.au{}&signature={}'.format(url, signature)

def ptv_api(url, dev_id, key):
    url = get_url(url, dev_id, key)
    payload = requests.get(url, verify=True)
    # print('GET ' + url)
    return payload.json()
