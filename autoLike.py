import tweepy
from config import CONFIG
import time
import sys
from datetime import datetime

def searchTweets(query):
    tweets = api.search(q=query, count=100)
    return tweets

def likeTweets(tweets, keyword_id):
    like_count = 0
    created_at = datetime.now().strftime("%Y%m%d%H%M%S")
    for tweet in tweets:
        #DB:ID KEYWORD_ID CREATED_AT USER_ID USER_NAME TWEET_ID CONTENT IS_FOLLOWER
        user_id = tweet.user._json['screen_name']
        user_name = tweet.user.name
        tweet_id = tweet.id
        content = tweet.text
        try:
            api.create_favorite(tweet_id) #フォロワーでなければいいねする
            #insertLikeRecord(keyword_id, created_at, user_id, user_name, tweet_id, content, is_follower) #結果をDBに保存する
            print("[INFO]likeレコードを追加しました。user_id:{}".format(user_id))
            like_count += 1
            print("[INFO]いいね数: {}".format(like_count))
        except Exception as e:
            print("[ERROR]いいねに失敗しました: {}".format(e))
            if e.response and e.response.status == 88:
                print("[INFO] rate limitの上限値を超えたので、15分待機後に実行します。")
                time.sleep(60 * 15)
            if e.response and e.response.status == 139:
                print("[ERROR] すでにいいねをしているツイートです")
    return like_count

if __name__ == '__main__':

    args = sys.argv
    query = args[1]
    print("[INFO]「{}」で検索したツイートを取得し、いいねします".format(query))

    # 各種ツイッターのキーをセット
    CONSUMER_KEY = CONFIG["CONSUMER_KEY"]
    CONSUMER_SECRET = CONFIG["CONSUMER_SECRET"]
    ACCESS_TOKEN = CONFIG["ACCESS_TOKEN"]
    ACCESS_SECRET = CONFIG["ACCESS_SECRET"]

    #Tweepy
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
    #APIインスタンスを作成
    api = tweepy.API(auth)

    tweets =  searchTweets(query)
    likeTweets(tweets, 0)
