# coding=utf-8

import json
from collections import defaultdict
from typing import Optional

import redis
import uvicorn
from fastapi import Body, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pydantic.json import Decimal
from sse_starlette.sse import EventSourceResponse

# from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from chartsInfo import draw_charts
from getStreamInfo import request
from prompt import Prompt
from utils.dbtool import get_sql_execute_result
from utils.redis_dependency import get_redis

# from setting import cretKey, uuid_str, dumps


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)


class ChatInput(BaseModel):
    input: str


# class Conversation:
#     """
#     存储对话信息
#     """
#
#     def __init__(self):
#         self.conversation_history: List[Dict] = []
#
#     def add_message(self, role, content):
#         message = {"role": role, "content": content}
#         self.conversation_history.append(message)

redis_pool = redis.ConnectionPool(host="localhost", port=6379, db=1)
r = redis.Redis(connection_pool=redis_pool)

app = FastAPI()

# 添加 CORS 中间件，允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)


@app.get("/refresh")
def refresh_page(r: redis.Redis = Depends(get_redis)):
    """刷新页面，清空redis缓存"""
    r.flushdb()
    return {"message": "Redis db=1 cache cleared!"}


@app.get("/")
def read_root():
    return {"message": "Hello World"}


# class Chatbot:
#     def __init__(self):
#         self.conversation = Conversation()


@app.get("/prompt")
def get_prompt():
    """
    前端获取提示语
    """
    prompt_base_chat = Prompt.base_prompt_chat
    prompt_base_query = Prompt.base_prompt_query
    prompt = {"promptBaseChat": prompt_base_chat, "promptBaseQuery": prompt_base_query}
    return {"code": 200, "data": prompt}


@app.post("/promptUpdate")
def update_prompt(prompt: str = Body(...), prompt_type: int = Body(...)):
    """
    前端更新提示语
    """
    print(prompt)
    try:
        if prompt_type == 1:
            prompt_base_chat = prompt
            Prompt.base_prompt_chat = prompt_base_chat
        elif prompt_type == 0:
            prompt_base_query = prompt
            Prompt.base_prompt_query = prompt_base_query
        else:
            return {"code": 501, "data": "Error: promptType error!"}
        return {"code": 200, "data": "success"}
    except Exception as e:
        return {"code": 502, "data": "Error: " + str(e)}


@app.get("/chat")
async def chat_stream(input: Optional[str] = None) -> EventSourceResponse:
    """
    查询入口
    """
    question = input
    base_prompt = "".join([Prompt.base_prompt_query, question])

    message = [{"role": "user", "content": base_prompt}]
    chat_msg = defaultdict(str)

    async def event_generator():
        """生成事件，获取流信息"""
        try:
            async for delta in request(message):
                if delta.get("role"):
                    chat_msg["role"] = delta.get("role")
                if delta.get("content"):
                    chat_msg["content"] += delta.get("content")
                yield dict(id=None, event=None, data=json.dumps(chat_msg))
        except Exception as e:
            print("error: ", e)

        sql_result = chat_msg["content"]
        print(sql_result)
        executed_result_dict = get_sql_execute_result(sql_result)
        print(executed_result_dict)
        if executed_result_dict["code"] == 200:
            executed_result = executed_result_dict["data"]
            draw_charts(executed_result)
        else:
            executed_result = executed_result_dict

        # 将执行结果存入redis，在本async方法中，无法直接返回执行结果，因为返回的是一个异步生成器
        # 因为对应前端方法，也不适合需要传参的asyncio的Future或者Queue
        if "Value" in sql_result or "GasFee" in sql_result or "GasPrice" in sql_result:
            # 处理Decimal类型
            r.set("sql_executed_result", json.dumps(executed_result, cls=DecimalEncoder))
        else:
            r.set("sql_executed_result", json.dumps(executed_result))

    return EventSourceResponse(event_generator())


@app.get("/multi-round-chat")
async def multi_chat_stream(input: Optional[str] = None) -> EventSourceResponse:
    """
    多轮对话查询入口
    """
    question = input
    base_prompt = Prompt.base_prompt_chat
    result_tmp = []
    try:
        length = int(r.get("len"))
    except Exception as e:
        print("First round! Outputs: ", e)
        length = 0
    for i in range(length):
        # 将字符串转化为Json
        item = json.loads(r.get(f"conversation:{i}"))
        result_tmp.append(item)
    message = {"default": result_tmp}
    # print(message)
    if not message["default"]:
        message = {"default": [{"role": "system", "content": base_prompt}]}
    if question is not None:
        message["default"].append({"role": "user", "content": question})
        # 输入为空的判定已经在前端实现

    print(message)
    chat_msg = defaultdict(str)

    async def event_generator():
        """生成事件，获取流信息"""
        try:
            async for delta in request(message["default"]):
                if delta.get("role"):
                    chat_msg["role"] = delta.get("role")
                if delta.get("content"):
                    chat_msg["content"] += delta.get("content")
                yield dict(id=None, event=None, data=json.dumps(chat_msg))
        except Exception as e:
            print("error: ", e)

        answer = chat_msg["content"]
        print(answer)
        message["default"].append({"role": "assistant", "content": answer})
        # todo，格式
        r.set("len", len(message["default"]))
        for i, item in enumerate(message["default"]):
            # Json转为字符串，然后才能放进redis
            r.set(f"conversation:{i}", json.dumps(item))
        # for item in message["default"]:  # todo，可能重复存入之前对话信息
        #     r.hset("rhash", item["role"], item["content"])
        if "您的问题已经足够清楚" in answer:
            # 是否调用查询数据库函数，选择权交还给前端用户
            print("清楚")
            r.set("isClear", "1")
        else:
            print("不清楚")
            r.set("isClear", "0")

        # todo，画图
        # if executed_result_dict["code"] == 200:
        #     executed_result = executed_result_dict["data"]
        #
        #     draw_charts(executed_result)
        # else:
        #     executed_result = executed_result_dict

    return EventSourceResponse(event_generator())


@app.get("/multi-round-chat/result")
def get_multichat_result():
    """
    前端通过获取多轮对话，从redis中返回
    """
    # 不要用r.hgetall("rhash")。哈希表此处不适合存储对话信息
    result_tmp = []
    length = int(r.get("len"))
    for i in range(length):
        # 从字符串转回Json
        item = json.loads(r.get(f"conversation:{i}"))
        result_tmp.append(item)
    result = {"default": result_tmp}
    result_tmp.append({"isClear": r.get("isClear").decode()})
    if result is not None:
        print(result)
        if isinstance(result, dict):
            # 正确结果
            return JSONResponse(
                status_code=200,
                content=result,
            )
        else:
            return JSONResponse(
                status_code=500,
                content=result,
            )
    else:
        return JSONResponse(
            status_code=204,
            content={"message": "no result"},
        )


@app.get("/chat/result")
def get_executed_result():
    """
    前端通过获取SQL执行结果，从redis中返回
    """
    result = r.get("sql_executed_result")
    r.delete("sql_executed_result")
    if result is not None:
        result = json.loads(result)
        print(result)
        if isinstance(result, dict):
            return result
            # 错误
        else:
            # 正确结果
            return JSONResponse(
                status_code=200,
                content=result,
            )
    else:
        return JSONResponse(
            status_code=204,
            content={"message": "no result"},
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": str(exc)},
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=4536, reload=True)
