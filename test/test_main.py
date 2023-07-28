import os
import sys

from fastapi.testclient import TestClient

from src.main import app  # 导入你的FastAPI实例

print(f"Current working directory: {os.getcwd()}")
print(f"sys.path: {sys.path}")

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
