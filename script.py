import requests

url = "https://2b9xkx83-2000.inc1.devtunnels.ms/api/v2/runtimes"
headers = {'X-Tunnel-Skip-Anti-Phishing-Page': 'true'}

try:
    response = requests.get(url, headers=headers)
    print(response.json())
except Exception as e:
    print(e)