from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent
)
import datetime
import os
import psycopg2

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


@handler.add(FollowEvent)
def handle_follow(event):
    # 若event.source.user_id沒有在資料庫就加入，若資料庫中已經有了就不用存了
    if isUserExist(event.source.user_id) == False:
        line_insert_userid(event.source.user_id)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    curTime = datetime.datetime.now()
    # 回報時間內，回傳"已回報完成，感謝您的配合並在時間內回報！"
    if checkInTime(datetime.time(curTime.hour, curTime.minute, curTime.second)):
        line_insert_messages(event.source.user_id, event.message.text)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="已回報完成，感謝您的配合！"))
        if isUserProfileNull(event.source.user_id) == None:
            line_insert_profile(event.message.text, event.source.user_id)
    # 回報時間外，回傳"現在非回報時間"
    else:
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="現在非回報時間，請在回報時間內回報！"))
    
def checkInTime(cur):
    d1 = datetime.time(10, 0, 0)
    d2 = datetime.time(11, 30, 59)
    d3 = datetime.time(18, 0, 0)
    d4 = datetime.time(19, 30, 59)
    d5 = datetime.time(21, 0, 0)
    d6 = datetime.time(22, 30, 59)
    return d1<= cur <= d2 or d3<= cur <= d4 or d5<= cur <= d6

def line_insert_userid(user_id):
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    # table_columns = ("user_id")
    insert_userid_query = '''
    INSERT INTO line_bot_users(user_id)
    VALUES (%s);
    '''
    cursor.execute(insert_userid_query, (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def line_insert_messages(user_id, message):
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    insert_message_query = '''
    INSERT INTO line_bot_messages(message, user_id)
    VALUES (%s, %s);
    '''
    cursor.execute(insert_message_query, (message, user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def line_insert_profile(message, user_id):
    user_no = int(message.split(" ")[0])
    user_name = message.split(" ")[1]
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    insert_profile_query = '''
    UPDATE line_bot_users
    SET user_name = %s, user_no = %s
    WHERE user_id = %s;
    '''
    cursor.execute(insert_profile_query, (user_name, user_no, user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def isUserExist(user_id):
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    search_user_query = '''
    SELECT EXISTS (SELECT 1 FROM line_bot_users WHERE user_id = %s);
    '''
    cursor.execute(search_user_query, (user_id,))
    isExist = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return isExist

def isUserProfileNull(user_id):
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    search_profile_query = '''
    SELECT user_no FROM line_bot_users WHERE user_id = %s;
    '''
    cursor.execute(search_profile_query, (user_id,))
    isProfileNull = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return isProfileNull

if __name__ == "__main__":
    app.run()