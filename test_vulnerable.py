import os

# 硬编码密钥
API_KEY = "sk-1234567890abcdef"

def query_db(user_input):
    # SQL 注入
    query = "SELECT * FROM users WHERE id = " + user_input
    os.system("echo " + user_input)
    return query