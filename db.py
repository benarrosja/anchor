import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv() # reads env files

def get_connection():
    print("MYSQL_HOST:",repr(os.getenv("MYSQL_HOST")))
    print("MYSQL_USER:", repr(os.getenv("MYSQL_USER")))
    print("MYSQL_PASSWORD:",repr(os.getenv("MYSQL_PASSWORD")))
    print("MYSQL_DB", repr(os.getenv("MYSQL_DB")))
    
    
    return mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DB"),
    )
    