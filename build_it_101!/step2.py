# -*- coding: utf-8 -*-
"""
@Time ： 2023/7/20 17:14
@Auth ： Ausdin Zhou
@File ：step2.py
@IDE ：PyCharm

turn on the stream mode to get the answer from openai
"""

import asyncio
import json
import os
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
        "stream": True,
    }
    async with AsyncClient() as client:
        async with client.stream(
            "POST", url, headers=headers, json=params, timeout=60
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                line = line.replace("data: ", "")
                try:
                    data = json.loads(line)
                except Exception:
                    data = {"choices": [{"finish_reason": "stop"}]}
                if data.get("choices")[0].get("finish_reason") is not None:
                    return
                yield data.get("choices")[0].get("delta")
                # pprint.pprint(response.json())


async def chat(question: str):
    message = [{"role": "user", "content": question}]
    async for delta in request(message):
        print(delta)


if __name__ == "__main__":
    asyncio.run(chat("你好，我是丁真"))
