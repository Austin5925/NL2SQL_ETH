import json

import requests


def get_abi(address):
    etherscan_api_key = '9SA795JPYP95TBMSVQT1KEWNUV3VI7Y7ZE'
    url = f"https://api.etherscan.io/api?module=contract&action=getabi" \
          f"&address={address}&apikey={etherscan_api_key}"
    response = requests.get(url)
    abi = json.loads(response.text)
    return abi
