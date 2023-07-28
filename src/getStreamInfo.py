import json
import os
from typing import AsyncGenerator, List

from dotenv import load_dotenv
from httpx import AsyncClient

load_dotenv()
api_key = os.getenv("API_KEY")
api_url = os.getenv("API_URL")


GPT_MODEL = "gpt-4"
GPT_TEMPERATURE = 0.3


async def request(val: List[dict[str, str]]) -> AsyncGenerator[dict, None]:
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
        "temperature": GPT_TEMPERATURE,
        "top_p": 1,
        "n": 1,
        "stream": True,
    }
    async with AsyncClient() as client:
        async with client.stream("POST", url, headers=headers, json=params, timeout=60) as response:
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
