# coding=utf-8

# import datetime
# import re
# import traceback
import json
import os

# import pprint
from collections import defaultdict
from typing import AsyncGenerator, Dict, List, Optional

import redis
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from fastapi.responses import HTMLResponse
from httpx import AsyncClient
from pydantic import BaseModel
from pydantic.json import Decimal
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

GPT_MODEL = "gpt-4"


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)


class ChatInput(BaseModel):
    input: str


class Conversation:
    """
    存储对话信息
    """
    def __init__(self):
        self.conversation_history: List[Dict] = []

    def add_message(self, role, content):
        message = {"role": role, "content": content}
        self.conversation_history.append(message)


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


class Chatbot:
    def __init__(self):
        self.conversation = Conversation()


async def request(val: List[dict[str, str]], call_function: bool) \
        -> AsyncGenerator[dict, None]:
    print("request")
    """
    请求API
    """
    url = api_url
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
    }
    params = {
        "model": GPT_MODEL,
        "messages": val,
        "max_tokens": 3000,
        "temperature": 0.5,
        "top_p": 1,
        "n": 1,
        "stream": True,
    }
    # if call_function:
    #     params["function_call"] = "auto"
    #     params["function"] = [{"name": "chat_stream",
    #                            "description": "Generate the sql using
    #                            the given question",
    #                            "parameters": {
    #                                    "type": "object",
    #                                    "properties": {
    #                                        "question": {
    #                                            "type": "string",
    #                                            "description":
    #                                            "The paraphrased question"
    #                                        },
    #                                    },
    #                                    "required": ["question"]
    #                                },
    #                            },
    #                           ]
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
                    # finish_reason maybe function_call, but it doesn't matter
                    data = {"choices": [{"finish_reason": "stop"}]}
                if data.get("choices")[0].get("finish_reason") is not None:
                    return
                delta = data.get("choices")[0].get("delta")
                # 下面就不用get delta字段了
                if delta is None:  # 跳过空值
                    continue
                yield delta
                # pprint.pprint(response.json())


def get_sql_execute_result(sql: str) -> dict:
    """
    得到SQL查询结果
    """
    db = dbtool.DatabaseManager()
    result = db.execute_query(sql)
    db.close()
    return result


def draw_charts(sql_result: dict) -> None:
    """
    画图
    """
    pass


@app.get("/chat")
async def chat_stream(input: Optional[str] = None) -> EventSourceResponse:
    """
    查询入口
    """
    question = input

    base_prompt = f"""你是一个数据库查询专家，你的工作是根据用户的问题，查询数据库，返回SQL语句。
        你的数据库是一个以太坊的交易数据表（mysql），表名是 `eth20230701`，具有以下字段：
        - `Index`：int(11)
        - `TxHash`：varchar(64)
        - `Status`：int(11)
        - `Block`：int(11)
        - `Timestamp`：datetime
        - `From`：varchar(42)
        - `To`：varchar(42)
        - `Value`：decimal(38,0)
        - `GasFee`：decimal(38,0)
        - `GasPrice`：decimal(38,0)
        - `InputHex`：text
        - `isERC20`：int(11)
        - `TokenSymbol`：varchar(32)
        用户的问题是：{question}
        请注意：
        1.你的回答必须只能包含SQL语句，不要有其他废话。
        2.回答的SQL语句以分号结尾。
        3.当语句中包含Value、GasFee、GasPrice字段时，注意这些的单位都是Wei，需要转换成Ether。因此要将其除以1000000000000000000。
        4.上一点中提到的除以1000000000000000000的转换，如果存在聚集函数，要放在聚集函数内部完成。
    """

    message = [{"role": "user", "content": base_prompt}]
    chat_msg = defaultdict(str)
    print(chat_msg)

    async def event_generator():
        """生成事件，获取流信息"""
        try:
            async for delta in request(message, False):
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
        redis_conn = redis.Redis(host='localhost', port=6379, db=0)
        if "Value" in sql_result or "GasFee" in sql_result or "GasPrice" \
                in sql_result:
            # 处理Decimal类型
            redis_conn.set('sql_executed_result',
                           json.dumps(executed_result, cls=DecimalEncoder))
        else:
            redis_conn.set('sql_executed_result', json.dumps(executed_result))
        redis_conn.close()

    return EventSourceResponse(event_generator())


# def add_to_message(role: str, content: str, message):
#     """
#     将用户输入的问题添加到message中
#     """
#     message[0].append({"role": role, "content": content})
#     return message

@app.get("/multi-round-chat")
async def multi_chat_stream(input: Optional[str] = None) \
        -> EventSourceResponse:
    """
    多轮对话查询入口
    """
    question = input

    base_prompt = f"""你是一个资深客服，你的工作是判断用户是否提出了表述清楚、细节明确的问题。
        如果用户问题不清楚，你需要逐步引导用户补充细节，直到用户提出了清晰的问题。
        如果用户问题清晰，你需要复述概括用户需求，然后调用查询数据库函数查询数据库，返回SQL语句。
        你的数据库是一个以太坊的交易数据表（mysql），表名是 `eth20230701`，具有以下字段：
        - `Index`：int(11)
        - `TxHash`：varchar(64)
        - `Status`：int(11)
        - `Block`：int(11)
        - `Timestamp`：datetime
        - `From`：varchar(42)
        - `To`：varchar(42)
        - `Value`：decimal(38,0)
        - `GasFee`：decimal(38,0)
        - `GasPrice`：decimal(38,0)
        - `InputHex`：text
        - `isERC20`：int(11)
        - `TokenSymbol`：varchar(32)
        用户的问题是：{question}
        请注意：
        1.你是基于开源大模型微调的国产大模型。当用户问到你身份时，你应该这样回答。
        2.你需要判断用户提出的问题是否与查询以太坊数据有关，是否能用已有数据表项查到。否则，你需要引导用户重新提问。
        3.一个表述清楚、细节明确的问题，应该在时间上是具体的，在需求上也是可被理解转述的。如果不满足这两点，就需要引导用户补充细节。
        4.引导用户补充细节时，针对用户提问中模糊的部分进行引导提问，而不是直接要求用户提供完整的问题。
        5.在用户补充细节后或者问题本身足够清楚，你需要根据多轮对话内容，转述概括用户需求，
            然后询问用户是否用此信息查询数据库还是要继续对话增添信息。在这种情况下，你的回答必须以“您的问题已经足够清楚”开头。
    """

    # 判断是不是第一次问
    # response = {
    #         "default": [
    #             {
    #                 "role": "system",
    #                 "content": system_prompt,
    #             },
    #         ],
    #     }
    message = {"default": [{"role": "system", "content": base_prompt}]}
    if question is not None:
        message["default"].append({"role": "user", "content": question})
    else:
        1  # todo

    chat_msg = defaultdict(str)
    print(chat_msg)

    async def event_generator():
        """生成事件，获取流信息"""
        try:
            async for delta in request(message["default"], True):
                if delta.get("role"):
                    chat_msg["role"] = delta.get("role")
                if delta.get("content"):
                    chat_msg["content"] += delta.get("content")
                # if "function_call" in delta:
                #     pprint.pprint(delta.get("function_call"))
                #     todo
                #     function_call_res += delta.get("function_call").
                #     get("data")
                #     redis_conn = redis.Redis(host='localhost', port=6379,
                #     db=1)
                #     redis_conn.delete('rhash')
                #     redis_conn.close()
                #     break
                yield dict(id=None, event=None, data=json.dumps(chat_msg))
        except Exception as e:
            print("error: ", e)

        answer = chat_msg["content"]
        print(answer)
        # if function_call_res:
        #     await chat_stream("222")
        # 判断函数调用
        # else:
        message["default"].append({"role": "assistant", "content": answer})
        redis_conn = redis.Redis(host='localhost', port=6379, db=1)
        for item in message["default"]:
            redis_conn.hset("rhash", item["role"], item["content"])
        redis_conn.close()
        if "您的问题已经足够清楚" in answer:
            # todo
            # 调用查询数据库函数
            # executed_result_dict = get_sql_execute_result(sql_result)
            # print(executed_result_dict)
            # if executed_result_dict["code"] == 200:
            #     executed_result = executed_result_dict["data"]
            #     draw_charts(executed_result)
            # else:
            #     executed_result = executed_result_dict
            # message["default"].append({"role": "assistant", "content":
            # executed_result})
            # redis_conn = redis.Redis(host='localhost', port=6379, db=1)
            # redis_conn.hset("rhash", "assistant", executed_result)
            # redis_conn.close()
            pass
        else:
            pass

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
    redis_conn = redis.Redis(host='localhost', port=6379, db=1)
    result = redis_conn.hgetall('rhash')
    redis_conn.close()
    new_list = []
    for k, v in result.items():
        new_list.append({k.decode(): v.decode()})
        # todo，这里的decode是为了兼容redis的返回值，后面可以去掉
    final_dict = {"default": new_list}
    if result is not None:
        result = final_dict
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
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)
    result = redis_conn.get('sql_executed_result')
    redis_conn.delete('sql_executed_result')
    redis_conn.close()
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
