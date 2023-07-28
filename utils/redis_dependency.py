import os

import redis


def get_redis():
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_db = int(os.getenv("REDIS_DB", 1))

    redis_pool = redis.ConnectionPool(host=redis_host, port=redis_port, db=redis_db)
    return redis.Redis(connection_pool=redis_pool)
