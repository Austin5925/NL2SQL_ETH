# # 数据库工具
#
# import threading
# import time
# import warnings
# from contextlib import contextmanager
# from functools import wraps
# from urllib.parse import urlparse, parse_qsl
# from dbutils.pooled_db import PooledDB

import os
import re

import pymysql
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv

load_dotenv()
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")


def get_sql_execute_result(sql: str) -> dict:
    """
    得到SQL查询结果
    """
    db = DatabaseManager()
    result = db.execute_query(sql)
    db.close()
    return result


class DatabaseManager:
    """
    使用连接池管理数据库连接
    """

    def __init__(
        self, host=db_host, user=db_user, port=db_port, password=db_password, database="eth_data"
    ):
        self.pool = PooledDB(
            creator=pymysql,  # 使用pymysql库
            maxconnections=0,  # 连接池允许的最大连接数，0表示不限制连接数
            mincached=4,  # 初始化时，连接池中至少创建的空闲的连接，0表示不创建
            maxcached=5,  # 连接池空闲的最多连接数，0和None表示不限制
            maxshared=3,
            blocking=True,  # 连接池中如果没有可用连接后，是否阻塞等待。True，等待；False，不等待然后报错
            host=host,
            user=user,
            password=password,
            database=database,
            autocommit=True,
        )

    def execute_query(self, query) -> dict:
        """
        执行查询
        """
        with self.pool.connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                query = self.check_schema(query)
                if query["code"] == 200:
                    sql_query = query["data"]
                    cur.execute(sql_query)
                    result = {"code": 200, "data": cur.fetchall()}
                else:
                    result = query
        return result

    def check_schema(self, query) -> dict:
        """
        检查sql语句是否符合要求
        """
        if "SELECT" in query:
            sql = "SELECT " + query.split("SELECT")[-1]
            match = re.search(r"(SELECT.*?;)", sql, re.DOTALL)
            if match:
                sql = match.group(1)
                return {"code": 200, "data": sql}
            else:
                return {"code": 5001, "error": "sql语句生成但未能正确执行，可能存在错误"}
        else:
            return {"code": 5002, "error": "答案中不包含sql语句"}

    def close(self):
        """
        关闭连接池
        """
        self.pool.close()


# import asyncio
#
# import pymysql
# import aiomysql
#
#
# class DatabaseManager:
#     """
#     使用连接池管理数据库连接
#     """
#
#     def __init__(
#         self, host="localhost", user="root", port=3306, password="111",
#             database="eth_data"
#     ):
#         self.loop = asyncio.get_event_loop()
#         self.pool = self.loop.run_until_complete(
#             aiomysql.create_pool(
#                 host=host, user=user, password=password, db=database,
#                 autocommit=True
#             )
#         )
#
#     # async def init_pool(self):
#     #     self.pool = await aiomysql.create_pool(self, loop=self.loop)
#
#     async def execute_query(self, query):
#         async with self.pool.acquire() as conn:
#             async with conn.cursor(aiomysql.DictCursor) as cur:
#                 await cur.execute(query)
#                 result = await cur.fetchall()
#         return result
#
#     async def close(self):
#         self.pool.close()
#         await self.pool.wait_closed()


#
# warnings.filterwarnings("ignore")
#
# from setting import dbUrl, Map
#
#
# def __parseresult_to_dict(parsed):
#     # 解析连接字符串
#     path_parts = parsed.path[1:].split('?')
#     query = parsed.query
#     connect_kwargs = {'db': path_parts[0]}
#     if parsed.username:
#         connect_kwargs['user'] = parsed.username
#     if parsed.password:
#         connect_kwargs['password'] = parsed.password
#     if parsed.hostname:
#         connect_kwargs['host'] = parsed.hostname
#     if parsed.port:
#         connect_kwargs['port'] = parsed.port
#
#     # Adjust parameters for MySQL.
#     if 'password' in connect_kwargs:
#         connect_kwargs['passwd'] = connect_kwargs.pop('password')
#
#     # Get additional connection args from the query string
#     qs_args = parse_qsl(query, keep_blank_values=True)
#     for key, value in qs_args:
#         if value.lower() == 'false':
#             value = False
#         elif value.lower() == 'true':
#             value = True
#         elif value.isdigit():
#             value = int(value)
#         elif '.' in value and all(p.isdigit() for p in value.split('.', 1)):
#             try:
#                 value = float(value)
#             except ValueError:
#                 pass
#         elif value.lower() in ('null', 'none'):
#             value = None
#         connect_kwargs[key] = value
#     if 'maxsize' in connect_kwargs:
#         connect_kwargs['maxconnections'] = connect_kwargs.pop('maxsize')
#     return connect_kwargs
#
#
# def __create_pool(url):
#     # 创建连接池
#     parsed = urlparse(url)
#     connect_kwargs = __parseresult_to_dict(parsed)
#     return PooledDB(pymysql, 1, **connect_kwargs)
#
#
# # 数据库连接
# global setting, transaction_map, pool
#
# if "transaction_map" not in globals():
#     global transaction_map
#     transaction_map = {}
#
# if "pool" not in globals():
#     global pool
#     pool = __create_pool(dbUrl)
#
#
# def __get_connection():
#     # 获取数据库链接
#     tid = threading.get_ident()
#     if tid in transaction_map:
#         return transaction_map.get(tid)
#     else:
#         return pool.connection()
#
#
# def __close_connection(conn):
#     # 归还数据库链接
#     tid = threading.get_ident()
#     if tid in transaction_map:
#         return
#     else:
#         conn.close()
#
#
# @contextmanager
# def dbp():
#     # with  数据库方法块
#     f = __get_connection()
#     yield f
#     __close_connection(f)
#
#
# def execute_sql(sql, params=None):
#     # 执行sql
#     with dbp() as db:
#         c = db.cursor()
#         c.execute(sql, params)
#         db.commit()
#         c.close()
#
#
# def execute_sql_list(sqls):
#     # 批量执行sql语句
#     with dbp() as db:
#         c = db.cursor()
#         for sql in sqls:
#             c.execute(sql)
#         db.commit()
#         c.close()
#
#
# def __get_obj_list_sql(obj_list, table, replace=True):
#     # 获取对象插入sql以及对应参数
#     if obj_list:
#         obj = obj_list[0]
#         keys = list(map(lambda x: f"`{x}`", obj.keys()))
#         values = list(map(lambda x: "%s", obj.keys()))
#         if replace:
#             sql = f"""replace INTO `{table}` ({",".join(keys)})
#             VALUES ({",".join(values)})"""
#         else:
#             sql = f"""insert IGNORE INTO `{table}` ({",".join(keys)})
#             VALUES ({",".join(values)})"""
#         params = []
#         for obj in obj_list:
#             params.append(tuple(obj.values()))
#         return sql, params
#     else:
#         return "", []
#
#
# def __get_obj_update_sql(obj, table, key):
#     # 获取对象插入sql以及对应参数
#     key_sql = f"where {key}='{obj[key]}'"
#     del obj[key]
#     keys = list(map(lambda x: f"`{x}`=%s", obj.keys()))
#     sql = f"""update  `{table}` set {",".join(keys)} """ + key_sql
#     params = tuple(obj.values())
#     return sql, params
#
#
# def sql_to_dict(sql, params=None):
#     # 查询sql，输出dict 列表
#     with dbp() as db:
#         c = db.cursor()
#         c.execute(sql, params)
#         ncols = len(c.description)
#         colnames = [c.description[i][0] for i in range(ncols)]
#         db_list = c.fetchall()
#         ret_list = []
#         for row in db_list:
#             d = Map()
#             for i in range(ncols):
#                 if isinstance(row[i], bytes) and len(row[i]) == 1:
#                     d[colnames[i]] = True if row[i] == b'\x01' else False
#                 else:
#                     d[colnames[i]] = row[i]
#             ret_list.append(d)
#         c.close()
#         return ret_list
#
#
# def start_transaction():
#     # 开始事务
#     conn = __get_connection()
#     conn.autocommit = False
#     tid = threading.get_ident()
#     transaction_map[tid] = conn
#     return tid
#
#
# def end_transaction(rockback=False):
#     # 结束事务
#     tid = threading.get_ident()
#     conn = transaction_map.pop(tid)
#     try:
#         if rockback:
#             conn.rollback()
#         else:
#             conn.commit()
#     finally:
#         conn.close()
#
#
# @contextmanager
# def transaction_code():
#     # with 事务方法块
#     f = start_transaction()
#     try:
#         yield f
#         end_transaction()
#     except Exception:
#         end_transaction(True)
#
#
# # 事务
# def transaction(target_function):
#     # 事务注解
#     @wraps(target_function)
#     def wrapper(*args, **kwargs):
#         start_transaction()
#         ret = target_function(*args, **kwargs)
#         end_transaction()
#         return ret
#
#     return wrapper
#
#
# def insert(obj, table, replace=False):
#     # 插入对象
#     (sql, params) = __get_obj_list_sql([obj], table, replace)
#     with dbp() as db:
#         c = db.cursor()
#         c.execute(sql, params[0])
#         db.commit()
#         lid = c.lastrowid
#         c.close()
#         return lid
#
#
# def update(obj, table, key="id"):
#     # 插入对象
#     (sql, params) = __get_obj_update_sql(obj, table, key)
#     with dbp() as db:
#         c = db.cursor()
#         c.execute(sql, params)
#         db.commit()
#         c.close()
#
#
# def inserts(obj_list, table, replace=False):
#     # 批量插入对象
#     if obj_list:
#         (sql, params) = __get_obj_list_sql(obj_list, table, replace)
#         with dbp() as db:
#             c = db.cursor()
#             c.executemany(sql, params)
#             db.commit()
#             c.close()
#
#
# def __update_setting():
#     global setting
#     s = sql_to_dict("select name,value from setting")
#     for i in s:
#         setting[i["name"]] = i["value"]
#
#
# def __update_setting_thread():
#     while True:
#         __update_setting()
#         time.sleep(5)
#
#
# # 系统设置
# if "setting" not in vars():
#     setting = Map()
#     __update_setting()
#     threading.Thread(target=__update_setting_thread, daemon=True).start()
#
#
# def get_table_desc(table):
#     datas = sql_to_dict(f"show full fields  from `{table}`")
#     ret_data = []
#     for v in datas:
#         ret_data.append(Map({"name": v.Field, "type": v.Type,
#         "commnet": v.Comment}))
#     return ret_data
