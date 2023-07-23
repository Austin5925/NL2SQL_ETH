# coding=utf-8
# import asyncio
# import datetime
#
# import pprint
# import re
# import traceback
import json
import os
from collections import defaultdict
from typing import AsyncIterable, List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from fastapi.responses import HTMLResponse
from httpx import AsyncClient
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

import dbtool

# from setting import cretKey, uuid_str, dumps

# 加载.env文件中的环境变量
load_dotenv()
api_key = os.getenv("API_KEY")
api_url = os.getenv("API_URL")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")


class ChatInput(BaseModel):
    input: str


app = FastAPI()

# 添加 CORS 中间件，允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


async def request(val: List[dict[str, str]]) -> AsyncIterable[str]:
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


async def draw_chart(sql: str) -> dict:
    """绘制图表"""
    db = dbtool.DatabaseManager()
    result = await db.execute_query(input)
    await db.close()
    return result


@app.get("/chat")
async def chat_stream(input: Optional[str] = None) -> EventSourceResponse:
    question = input

    base_prompt = f"""
        你是一个数据库查询专家，你的工作是根据用户的问题，查询数据库，返回SQL语句。
        你的数据库是一个以太坊的交易数据表（mysql），表名是 `eth20230701`，具有以下字段：：
        - `Index`：int(11)
        - `TxHash`：varchar(64)
        - `Status`：int(11)
        - `Block`：int(11)
        - `Timestamp`：datetime
        - `From`：varchar(42)
        - `To`：varchar(42)
        - `Value`：decimal(38,0)
        - `GasFee`：decimal(38,0)
        - `GasPrice`：decimal(20,0)
        - `InputHex`：text
        - `isERC20`：int(11)
        - `TokenSymbol`：varchar(32)
        用户的问题是：{question}
        请注意：
        1. 你的回答只需要包含SQL语句。
    """

    message = [{"role": "user", "content": base_prompt}]
    chat_msg = defaultdict(str)
    print(chat_msg)

    async def event_generator():
        async for delta in request(message):
            if delta.get("role"):
                chat_msg["role"] = delta.get("role")
            if delta.get("content"):
                print(delta.get("content"))
                chat_msg["content"] += delta.get("content")
                yield dict(id=None, event=None, data=json.dumps(chat_msg))
                # await asyncio.sleep(0.1)

    result = chat_msg["content"]
    draw_chart(result)

    return EventSourceResponse(event_generator())


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": str(exc)},
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=4536, reload=True)
