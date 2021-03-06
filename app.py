import tweepy
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, logging, Response, redirect, flash
from contextlib import closing    # ここはオフィシャルにはなかったが必要だった
import sqlite3
from config import CONFIG
import time
import os
from crontab import CronTab


# 各種ツイッターのキーをセット
CONSUMER_KEY = CONFIG["CONSUMER_KEY"]
CONSUMER_SECRET = CONFIG["CONSUMER_SECRET"]
ACCESS_TOKEN = CONFIG["ACCESS_TOKEN"]
ACCESS_SECRET = CONFIG["ACCESS_SECRET"]

#FLASKのキーの設定
SECRET_KEY = CONFIG["SECRET_KEY"]

#Tweepy
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
#APIインスタンスを作成
api = tweepy.API(auth)

# データベースの接続、なければ作成
DATABASE = "db/database.db"
conn = sqlite3.connect(DATABASE)
c = conn.cursor()
create_query_db_sql = "CREATE TABLE IF NOT EXISTS query (id integer PRIMARY KEY, query text, cron_tab text, is_enabled integer default 0)"
create_like_history_sql = "CREATE TABLE IF NOT EXISTS like_history (id integer PRIMARY KEY, query_id integer, created_at TIMESTAMP, user_id text, user_name text, tweet_id text, content text, is_follower int)"
create_followers_sql = "CREATE TABLE IF NOT EXISTS followers (id integer PRIMARY KEY, created_at TIMESTAMP, followers_count integer)"
c.execute(create_query_db_sql)
c.execute(create_like_history_sql)
c.execute(create_followers_sql)
conn.close()

# Flask の起動
app = Flask(__name__)

# Viewの処理

@app.route('/index')
def queryList():
    cron = CronTab(user=True)
    return render_template('queryList.html', queryList = getAllQuery(), cron = cron)

@app.route("/edit/<id>", methods=['GET', 'POST'])
def editQuery(id):
    if request.method == 'POST':
        crontab = request.values.get('crontab') # Your form's
        isEnabled = request.values.get('is_enabled') # input names
        isEnabled = 1 if isEnabled == "on" else 0 #ON = 1, OFF = 0
        updateQuery(id, crontab, isEnabled)
        query = selectQueryById(id)[1]
        print(query)
        if isEnabled == 1:
            print("[INFO] CRONの有効化設定が選ばれました。有効化します。")
            enableCronTab(query, crontab)
        else:
            print("[INFO] CRONの無効化設定が選ばれました。無効化します。")
            disableCronTab(query, crontab)
        return redirect("/index")
    res = selectQueryById(id)
    return render_template('editQuery.html', res = res)

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/you')
def yourProfile():
    return render_template('yourProfile.html')

@app.route('/you/followings')
def followings():
    return render_template("followings.html")

@app.route('/you/followers')
def followers():
    return render_template("followers.html")

@app.route('/show/<id>')
def showQuery(id):
    queryList = getQueryById(id)
    query = getQueryFromQueryId(id)
    return render_template('query.html', queryList = queryList, query = query)


@app.route('/like/<id>/')
def like(id):
    query = getQueryFromQueryId(id)
    print(query[0])
    tweets = searchTweets(query)
    like_count = likeTweets(tweets, id)
    flash("{}件のツイートをいいねしました".format(like_count))
    return redirect("/show/{}".format(id))

@app.route('/delete/<id>/')
def deleteQuery(id):
    deleteCronTab(id)
    deleteQueryFromQueryId(id)
    return redirect("/index")

@app.route('/addQuery', methods=['GET', 'POST'])
def addQuery():
    if request.method == 'POST':
        query = request.form['query']
        cron = request.form['cron']
        insertQuery(query, cron)
        addCronTab(query, cron)
        return redirect('/index')
    return render_template('addQuery.html')

@app.route("/you/followers/update")
def updateFollwers():
    """
    フォロワー数を更新し、プロフィールページにリダイレクトします
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        followersIds = getFollowers_Ids()
        created_at = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        insertSQL = "INSERT INTO followers (created_at, followers_count) VALUES (?,?)"
        c.execute(insertSQL, [created_at, len(followersIds)])
        csvName = "{}.csv".format(created_at)
        exportFollowerCSV(csvName, getFollowers_Ids()) #CSVを/csv/followers配下にエクスポート
    except Exception as e:
        print(e)
    return redirect('/you')

@app.route('/dropDB')
def dropDB():
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        dropSQL = "DROP TABLE query;"
        c.execute(dropSQL)
        c.close()
        print("[INFO] データベースを初期化しました")
        return redirect("/")
    except Exception as e:
        print(e)
    return redirect('/')

@app.route('/', methods=['POST'])
def getData():

    #CSVを初期化
    df = pd.read_csv('tweet.csv') # tweetedTime query userid username content tweetURL

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
        se = pd.Series(
            [tweetedTime, query, user_id, username, content],
            ['tweetedTime', 'query', 'userid', 'username', 'content']
            ) # 取得したページのURL, 色, サイズと在庫の行を追加し
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
def selectQueryById(queryId):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    insertSQL = "SELECT * FROM query WHERE id = ?"
    res = c.execute(insertSQL, [queryId]).fetchone()
    c.close()
    return res

def updateQuery(id, crontab, isEnabled):
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        updateSQL = "UPDATE query SET cron_tab = ?, is_enabled = ? WHERE id = ?"
        c.execute(updateSQL, [crontab, isEnabled, id])
        conn.commit()
        c.close()
        print("[INFO]キーワードを更新しました")
    except Exception as e:
        print("[ERROR]キーワードの更新に失敗しました: {}".format(e))

def insertQuery(query, crontab):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    insertSQL = "INSERT INTO query (query, cron_tab) VALUES (?, ?)"
    c.execute(insertSQL, [query, crontab])
    conn.commit()
    c.close()

def getAllQuery():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    selectAllSQL = "SELECT * FROM query ORDER BY id DESC"
    res = c.execute(selectAllSQL)
    return res

def getLikedUserIds(query_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()


    selectAllSQL = "SELECT user_id FROM like_history WHERE query_id = ?"
    res = c.execute(selectAllSQL, [query_id])
    user_ids = list(res.fetchall())
    return user_ids

def getUserName(user_id):
    user = api.get_user(783214)
    user_name = user.name
    return user_name

def getQueryById(id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    selectAllSQL = "SELECT * FROM like_history WHERE query_id = ? ORDER BY id DESC"
    res = c.execute(selectAllSQL,[id])
    return res

def getQueryFromQueryId(id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    selectIdSQL = "SELECT query FROM query WHERE id = ?"
    c.execute(selectIdSQL,[id])
    return c.fetchone()

def deleteQueryFromQueryId(id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    deleteQuerySQL = "DELETE FROM query WHERE id = ?"
    c.execute(deleteQuerySQL,[id])
    conn.commit()
    c.close()

def insertLikeRecord(keyword_id, created_at, user_id, user_name, tweet_id, content, is_follower):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    insertSQL = "INSERT INTO like_history (query_id, created_at, user_id, user_name, tweet_id, content, is_follower) VALUES (?,?,?,?,?,?,?)"
    c.execute(insertSQL, [keyword_id, created_at, user_id, user_name, tweet_id, content, is_follower])
    conn.commit()
    c.close()

# Tweepyの関数群
def likeTweets(tweets, keyword_id):
    like_count = 0
    followers_ids = getFollowers_Ids()
    created_at = datetime.now().strftime("%Y%m%d%H%M%S")
    for tweet in tweets:
        #DB:ID KEYWORD_ID CREATED_AT USER_ID USER_NAME TWEET_ID CONTENT IS_FOLLOWER
        user_id = tweet.user._json['screen_name']
        user_name = tweet.user.name
        tweet_id = tweet.id
        content = tweet.text
        is_follower = 1 if user_id in followers_ids else 0 #フォロワーのユーザー名の中にそのユーザーが存在すれば1
        try:
            api.create_favorite(tweet_id) #フォロワーでなければいいねする
            insertLikeRecord(keyword_id, created_at, user_id, user_name, tweet_id, content, is_follower) #結果をDBに保存する
            print("[INFO]likeレコードを追加しました。user_id:{}".format(user_id))
            like_count += 1
            print("[INFO]いいね数: {}".format(like_count))
        except Exception as e:
            print("[ERROR]いいねに失敗しました: {}".format(e))
            if e.response and e.response.status == 429:
                print("[INFO] rate limitの上限値を超えたので、15分待機後に実行します。")
                time.sleep(60 * 15)
            if e.response and e.response.status == 139:
                print("[ERROR] すでにいいねをしているツイートです")
    return like_count


def searchTweets(query):
    tweets = api.search(q=query, count=100)
    return tweets

def getFollowers_Ids():
    followers = tweepy.Cursor(api.followers_ids, cursor = -1).items()
    followers_ids = []
    try:
        for followers_id in followers:
            print(followers_id)
            followers_ids.append(followers_id)
    except tweepy.error.TweepError as e:
        print (e.reason)
    return followers_ids

def getFollowersUserIds():
    follower_screen_names = []
    for follower in api.followers_ids():
        follower_screen_names.append(api.get_user(follower).screen_name)
    print("{}名のフォロワー数を取得しました".format(len(follower_screen_names)))
    return follower_screen_names

def getStats(query_id):
    """
    キーワードIDから、いいねしたユーザーのID・フォローバックしてくれたユーザーのIDを返します。
    """
    try:
        liked_user_ids = getLikedUserIds(query_id) #いいねしたユーザーIDを取り出す
        print(liked_user_ids)
        follower_user_ids = getFollowersUserIds() #フォロワーのユーザーIDを取り出す
        print(follower_user_ids)
        follow_back_user_ids = [] #いいねしていてかつフォロワーのユーザーIDを取り出す
        for liked_user_id in liked_user_ids:
            if liked_user_id in follower_user_ids:
                print("{} follows back you".format(liked_user_id))
                follow_back_user_ids.append(liked_user_id)
        res = {
            "liked_user_ids": liked_user_ids,
            "follow_back_user_ids": follow_back_user_ids
        }
        return res
    except Exception as e:
        print(e)
        res = {
            "liked_user_ids": "FAILED",
            "follow_back_user_ids": "FAILED"
        }
        return res

def exportFollowerCSV(created_at, followers_ids):
    """
    フォロワー数更新時に、フォロワー数の詳細データをCSVにエクスポートします
    user_id,user_name,followings_count,followers_count
    """
    df = pd.DataFrame(columns=["user_id","user_name","followings_count","followers_count"])
    for user_id in followers_ids:
        try:
            user_name = getUserName(user_id)
            print (user_name)
            followings_count = getFollowingsCount(user_id)
            followers_count = getFollowersCount(user_id)
            se = pd.Series(
                [user_id, user_name, followings_count, followers_count],
                ["user_id","user_name","followings_count","followers_count"]
                )
            df = df.append(se, ignore_index=True)
            print(df)
        except Exception as e:
            print("[ERROR] データの取得に失敗しました：{}".format(e))
            print("[INFO] 15分間待機します")
            time.sleep(60 * 15)
            continue
    df.to_csv("csv/followers/{}".format(created_at))


def getFollowersCount(user_id):
    try:
        user = api.get_user(user_id)
        followersCount = user.followers_count
        return followersCount
    except Exception as e:
        print("[ERROR] フォロワー数の取得に失敗しました:{}".format(e))

def getFollowingsCount(user_id):
    try:
        user = api.get_user(user_id)
        followingCount = user.friends_count
        return followingCount
    except Exception as e:
        print("[ERROR]フォロー数の取得に失敗しました。{}".format(e))

#Crontabの関数群

def addCronTab(query, crontab):
    cron = CronTab(user=True)
    cwd = os.getcwd()
    job = cron.new(command = "python3 {}/autolike.py {}".format(cwd, query))
    job.enable(False)
    cron.write()
    print("[INFO] crontabを新しく追加しました")

def enableCronTab(query, crontab):
    if crontab:
        cron = CronTab(user=True)
        jobs = cron.find_command(query)
        for job in jobs:
            print("[INFO] 以下のジョブがみつかりました:{}".format(job))
            if not job.is_enabled():
                job.enable()
                cron.write()
                print("[INFO] 以下のJOBを有効化しました：{}".format(job))

def disableCronTab(query, crontab):
    cron = CronTab(user=True)
    jobs = cron.find_command(query)
    for job in jobs:
        job.enable(False)
        cron.write()
        print("[INFO] 以下のJOBを無効化しました：{}".format(job))

def deleteCronTab(id):
    query = selectQueryById(id)[1]
    print("query:{}".format(query))
    cron = CronTab(user=True)
    jobs = cron.find_command(query)
    for job in jobs:
        cron.remove(job)
        cron.write()
        print("[INFO] 以下のJOBを削除しました:{}".format(query))

if __name__ == '__main__':
    app.secret_key = SECRET_KEY
    app.run(debug=True) # デバックしたときに、再ロードしなくても大丈夫になる
