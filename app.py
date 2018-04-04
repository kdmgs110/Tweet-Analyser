import tweepy
import pandas
from datetime import datetime
from flask import Flask, render_template, request, logging, Response, redirect, flash
from contextlib import closing    # ここはオフィシャルにはなかったが必要だった
import sqlite3

# 各種ツイッターのキーをセット
CONSUMER_KEY = ''
CONSUMER_SECRET = ''
ACCESS_TOKEN = ''
ACCESS_SECRET = ''
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
#APIインスタンスを作成
api = tweepy.API(auth)

# データベースの接続、なければ作成
DATABASE = "db/database.db"
conn = sqlite3.connect(DATABASE)
c = conn.cursor()
create_query_db_sql = "CREATE TABLE IF NOT EXISTS query (id integer PRIMARY KEY,query text)"
create_like_history_sql = "CREATE TABLE IF NOT EXISTS like_history (id integer PRIMARY KEY, query_id integer, created_at TIMESTAMP, user_id text, user_name text, tweet_id text, content text)"

c.execute(create_query_db_sql)
c.execute(create_like_history_sql)
conn.close()

# Flask の起動
app = Flask(__name__)

# Viewの処理

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/index')
def queryList():
    return render_template('queryList.html', queryList = getAllQuery())

@app.route('/show/<id>')
def showQuery(id):
    return render_template('query.html')


@app.route('/like/<id>/')
def like(id):
    query = getQueryFromQueryId(id)
    tweets = searchTweets(query)
    likeTweets(tweets)
    #flash("10件のツイートをいいねしました", 'info')
    return redirect("/show/{}".format(id))

@app.route('/delete/<id>/')
def deleteQuery(id):
    deleteQueryFromQueryId(id)
    return redirect("/index")

@app.route('/addQuery', methods=['GET', 'POST'])
def addQuery():
    if request.method == 'POST':
        query = request.form['query']
        cron = request.form['cron']
        insertQuery(query)
        return redirect('/index')

    return render_template('addQuery.html')

@app.route('/', methods=['POST'])
def getData():

    #CSVを初期化
    df = pandas.read_csv('tweet.csv') # tweetedTime query userid username content tweetURL

    #実行時刻
    time = datetime.now().strftime("%Y%m%d%H%M")
    #検索クエリを取得
    query = request.form["query"]
    print(query)

    #Tweepyへのauth
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)

    #APIインスタンスを作成
    api = tweepy.API(auth)
    search_results = api.search(q=query, count=count)

    #検索結果から値を取得
    for result in search_results:

        #ツイート作成時刻
        tweetedTime = result.created_at

        #ユーザーID
        user_id = result.id #ツイートのstatusオブジェクトから、ツイートidを取得

        #ユーザー名
        username = result.user._json['screen_name']

        #ツイート内容
        content = result.text

        #CSVに行を追加
        se = pandas.Series([tweetedTime, query, user_id, username, content],['tweetedTime', 'query', 'userid', 'username', 'content']) # 取得したページのURL, 色, サイズと在庫の行を追加し
        df = df.append(se, ignore_index=True) # データフレームに追加する
        print(df)

    csvName = "{}.csv".format(time)
    df.to_csv(csvName)
    with open(csvName) as fp:
        csv = fp.read()
        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename={}".format(csvName)})

# SQL関係のメソッド

def insertQuery(query):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    insertSQL = "INSERT INTO query (query) VALUES (?)"
    c.execute(insertSQL, [query])
    conn.commit()
    c.close()

def getAllQuery():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    selectAllSQL = "SELECT * FROM query ORDER BY id DESC"
    res = c.execute(selectAllSQL)
    return res

def getQueryFromQueryId(id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    selectIdSQL = "SELECT query FROM query WHERE id = ?"
    res = c.execute(selectIdSQL,[id])
    return res

def deleteQueryFromQueryId(id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    deleteQuerySQL = "DELETE FROM query WHERE id = ?"
    c.execute(deleteQuerySQL,[id])
    conn.commit()
    c.close()

def insertLikeRecord(id, keyword_id, created_at, user_id, user_name, tweet_id, content):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    insertSQL = "INSERT INTO "
    c.execute(insertSQL,[id])
    conn.commit()
    c.close()

# Tweepyの関数群
def likeTweets(tweets):
    for tweet in tweets:
        #DB:ID KEYWORD_ID CREATED_AT USER_ID USER_NAME TWEET_ID CONTENT
        user_id = tweet.user._json['screen_name']
        user_name = tweet.user.name
        tweet_id = tweet.id
        content = tweet.text
        try:
            api.create_favorite(user_id) #いいねする
            insertLikeRecord() #結果をDBに保存する
        except Exception as e:
            print ("ERROR: スキップしました: " + e)


def searchTweets(query):
    tweets = api.search(q=query, count=100)
    return tweets


if __name__ == '__main__':
    app.run(debug=True) # デバックしたときに、再ロードしなくても大丈夫になる
