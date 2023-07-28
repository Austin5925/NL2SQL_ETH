import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()
etherscan_api_key = os.getenv("ETHERSCAN_API_KEY")


def get_abi(address):
    url = f"https://api.etherscan.io/api?module=contract&action=getabi" \
          f"&address={address}&apikey={etherscan_api_key}"
    response = requests.get(url)
    abi = json.loads(response.text)
    return abi
