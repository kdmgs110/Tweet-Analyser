import sqlite3

DATABASE = 'database.db'

conn = sqlite3.connect(DATABASE) #データベースに接続
c = conn.cursor()
    
# データベースの作成
create_db_sql = """CREATE TABLE IF NOT EXISTS　client(name string, client_id string, client_secret string, redirect_uri string)"""
c.execute(create_db_sql)
