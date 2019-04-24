import requests
import json

url = "http://localhost:5000/nodes/resolve"
req = requests.get(url=url)
if req.json()['message'] == 'Our chain is authoritative':
    print('TRUE')
