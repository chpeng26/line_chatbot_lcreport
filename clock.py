from apscheduler.schedulers.blocking import BlockingScheduler
import datetime

from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
import datetime
import os
import psycopg2
import urllib

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ['CHANNEL_ACCESS_TOKEN']
CHANNEL_SECRET = os.environ['CHANNEL_SECRET']

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

def line_get_userid():
    user_id = []
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    select_userid_query = '''
    SELECT user_id FROM line_bot_users;
    '''
    cursor.execute(select_userid_query)
    for user in cursor.fetchall():
        user_id.append(user[0])
    return user_id

def line_get_message():
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    select_message_query = '''
    SELECT DISTINCT ON(user_no) line_bot_users.user_no, message, line_bot_messages.create_time 
    FROM line_bot_messages, line_bot_users
    WHERE line_bot_messages.user_id = line_bot_users.user_id 
    AND line_bot_users.user_no < 10000 
    AND NOW()-INTERVAL'1hours 20 minutes' <=line_bot_messages.create_time 
    AND line_bot_messages.create_time <= NOW()
    ORDER BY user_no ASC, create_time DESC;
    '''
    cursor.execute(select_message_query)
    messages = ""
    for message in cursor.fetchall():
        time = message[2]
        messages  += "{text} {time}\n".format(text = message[1], time = "{hour}:{minute}".format(hour = time.hour + 8, minute = time.minute))
    return messages

sched = BlockingScheduler()

@sched.scheduled_job('cron', hour='11, 19, 22', minute = '20')
def push_organized_message():
    owner_id = os.environ['OWNER_ID']
    print('This job is run 11:20, 19:20, 22:20')
    messages = line_get_message()
    try:
        line_bot_api.push_message(owner_id, TextSendMessage(text=messages))
    except:
        print("push message error")

@sched.scheduled_job('cron', hour='10, 18, 21')
def push_multicast_message():
    print('This job is run 10:00, 18:00, 21:00')
    curTime = datetime.datetime.now()
    user_id = line_get_userid() #先取得user_id
    line_bot_api.multicast(
        user_id, 
        TextSendMessage(text = '{month}/{day} 回報時間 {hour}:00-{hour}:30 並回報健康狀況'.format(month = curTime.month, day = curTime.day, hour = curTime.hour + 1)))

@sched.scheduled_job('cron', minute='*/20')
def scheduled_job2(): # to avoid dyno sleeping
    print('This job is run every day at every twenty miniutes')
    url = "https://lungchiuanreporter.herokuapp.com/"
    conn = urllib.request.urlopen(url)
sched.start()
