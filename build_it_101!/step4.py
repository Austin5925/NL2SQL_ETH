# -*- coding: utf-8 -*-
"""
@Time ： 2023/7/21 14:34
@Auth ： Ausdin Zhou
@File ：step4.py
@IDE ：PyCharm

add the fastapi framework
"""


import json
import os
from collections import defaultdict
from typing import List

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient

# 加载.env文件中的环境变量
load_dotenv()
api_key = os.getenv("API_KEY")
api_url = os.getenv("API_URL")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

app = FastAPI()

# 添加 CORS 中间件，允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)


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
                delta = data.get("choices")[0].get("delta")
                # 下面就不用get delta字段了
                if delta is None:  # 跳过空值
                    continue
                yield delta
                # pprint.pprint(response.json())


@app.websocket("/chat")
async def chat(websocket: WebSocket):
    await websocket.accept()
    message = []
    while True:
        data = await websocket.receive_text()
        if data == "quit":
            await websocket.close()
            break
        message = [{"role": "user", "content": data}]
        chat_msg = defaultdict(str)
        async for delta in request(message):
            if delta.get("role"):
                chat_msg["role"] = delta.get("role")
            if delta.get("content"):
                chat_msg["content"] += delta.get("content")
                await websocket.send_text(delta.get("content"))
        message.append(chat_msg)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=4536, reload=True)
