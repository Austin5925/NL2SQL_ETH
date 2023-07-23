# -*- coding: utf-8 -*-
"""
@Time ： 2023/7/20 16:45
@Auth ： Ausdin Zhou
@File ：step1.py
@IDE ：PyCharm

get the answer from openai in a non-stream way
"""

import asyncio
import os
import pprint
from typing import List

from dotenv import load_dotenv
from httpx import AsyncClient

# 加载.env文件中的环境变量
load_dotenv()
api_key = os.getenv("API_KEY")
api_url = os.getenv("API_URL")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")


async def request(val: List[dict[str, str]]):
    url = api_url
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
    }
    params = {
        "model": "gpt-3.5-turbo",
        "messages": val,
        "max_tokens": 2000,
        "temperature": 0.8,
        "top_p": 1,
        "n": 1,
        "stream": False,
    }
    async with AsyncClient() as client:
        response = await client.post(url=url, headers=headers, json=params)
        pprint.pprint(response.json())


if __name__ == "__main__":
    asyncio.run(request([{"role": "user", "content": "Say this is a test!"}]))
