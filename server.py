#-*-coding:utf-8-*-

from flask import Flask, render_template, request, jsonify, make_response, redirect
from hashlib import md5
import base64
import os
import json
import sqlite3
import redis

app = Flask(__name__)
app.debug = True

SUCCESS = '00000'
PARAMETER_ERROR = '10001'
USERNAME_EXIST = '10002'
PASSWORD_TOO_SHORT = '10003'
EMAIL_EXIST = '10004'
TOKEN_NOT_EXIST = '10005'
EMAIL_NOT_EXIST = '10006'
PASSWORD_ERROR = '10007'
UID_ERROR = '10008'
TEAM_NAME_EXIST = '10009'

conn = sqlite3.connect('smp.db', check_same_thread=False)
cursor = conn.cursor()

r = redis.Redis(host='localhost', port=6379)

def generate_token():
    code = ''.join(map(lambda xx:(hex(ord(xx))[2:]),os.urandom(16)))
    while True:
        if r.sismember('smptoken',code) == False:
            r.sadd('smptoken',code)
            break
        code = ''.join(map(lambda xx:(hex(ord(xx))[2:]),os.urandom(16)))
    return code

def check_username_email_exist(username, email):
    tmp = cursor.execute('select * from user where username="%s"'%username).fetchall()
    if len(tmp) != 0:
        return USERNAME_EXIST
    tmp = cursor.execute('select * from user where email="%s"'%email).fetchall()
    if len(tmp) != 0:
        return EMAIL_EXIST
    return SUCCESS

def send_verify_email(username, password, email):
    tmp = check_username_email_exist(username, email)
    if tmp != SUCCESS:
        return tmp

    verify_token = generate_token()
    user_info = json.dumps({'username':username, 'password':password, 'email':email})
    r.set(verify_token, user_info, 7200)

    verify_url = 'http://smp-challenge.com/verify/%s'%verify_token
    print verify_url

    return SUCCESS

def check_verify(code):
    user_info = r.get(code)
    if user_info is None:
        return None, None, None

    r.delete(code)
    user_info = json.loads(user_info)
    return user_info['username'], user_info['password'], user_info['email']

def add_user(username, password, email):
    cursor.execute('insert into user values (NULL, "%s", "%s", "%s")'%(username, password, email))
    conn.commit()
    return SUCCESS

def check_login(email, password):
    tmp = cursor.execute('select * from user where email="%s" and password="%s"'%(email, password)).fetchall()
    if len(tmp) != 0:
        token = generate_token()
        r.set('smptoken:'+token, tmp[0][0], 7200)
        return SUCCESS, token
    else:
        return PASSWORD_ERROR, None

def token2uid(token):
    uid = r.get('smptoken:' + token)
    if uid is None:
        return TOKEN_NOT_EXIST, None
    else:
        return SUCCESS, uid

def uid2username(uid):
    tmp = cursor.execute('select username from user where uid=%s'%uid).fetchall()
    if len(tmp) != 0:
        return SUCCESS, tmp[0][0]
    else:
        return UID_ERROR, None

def update_team_by_uid(uid, teamname, members):
    tmp = cursor.execute('select teamname from team where teamname="%s" and uid != %s'%(teamname, uid)).fetchall()
    if len(tmp) != 0:
        return TEAM_NAME_EXIST

    members = base64.b64encode(json.dumps(members))
    tmp = cursor.execute('select uid from team where uid=%s'%uid).fetchall()
    if len(tmp) != 0:
        cursor.execute('update team set teamname="%s",members="%s" where uid=%s'%(teamname, members, uid))
    else:
        cursor.execute('insert into team values (%s, "%s", "%s")'%(uid, teamname, members))
    conn.commit()
    return SUCCESS

def uid2team(uid):
    tmp = cursor.execute('select teamname,members from team where uid=%s'%uid).fetchall()
    if len(tmp) == 0:
        return UID_ERROR, None, None
    else:
        return SUCCESS, tmp[0][0], json.loads(base64.b64decode(tmp[0][1]))

@app.route('/', methods=['GET'])
def index():
    cookies = request.cookies
    if not 'token' in cookies:
        return render_template('index.html')
    token = cookies['token']

    status, uid = token2uid(token)
    if status != SUCCESS:
        res = make_response(render_template('index.html'))
        res.delete_cookie('token')
        return res

    status, username = uid2username(uid)
    if status != SUCCESS:
        res = make_response(render_template('index.html'))
        res.delete_cookie('token')
        return res

    res = make_response(render_template('index.html', login=True, username=username))
    res.set_cookie('token', token)
    return res

@app.route('/challenge', methods=['GET'])
def challenge():
    cookies = request.cookies
    if not 'token' in cookies:
        return render_template('challenge.html')
    token = cookies['token']

    status, uid = token2uid(token)
    if status != SUCCESS:
        res = make_response(render_template('challenge.html'))
        res.delete_cookie('token')
        return res

    status, username = uid2username(uid)
    if status != SUCCESS:
        res = make_response(render_template('challenge.html'))
        res.delete_cookie('token')
        return res

    res = make_response(render_template('challenge.html', login=True, username=username))
    res.set_cookie('token', token)
    return res

@app.route('/dataset', methods=['GET'])
def dataset():
    cookies = request.cookies
    if not 'token' in cookies:
        return render_template('dataset.html')
    token = cookies['token']

    status, uid = token2uid(token)
    if status != SUCCESS:
        res = make_response(render_template('dataset.html'))
        res.delete_cookie('token')
        return res

    status, username = uid2username(uid)
    if status != SUCCESS:
        res = make_response(render_template('dataset.html'))
        res.delete_cookie('token')
        return res

    res = make_response(render_template('dataset.html', login=True, username=username))
    res.set_cookie('token', token)
    return res

@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    cookies = request.cookies
    if not 'token' in cookies:
        return render_template('leaderboard.html')
    token = cookies['token']

    status, uid = token2uid(token)
    if status != SUCCESS:
        res = make_response(render_template('leaderboard.html'))
        res.delete_cookie('token')
        return res

    status, username = uid2username(uid)
    if status != SUCCESS:
        res = make_response(render_template('leaderboard.html'))
        res.delete_cookie('token')
        return res

    res = make_response(render_template('leaderboard.html', login=True, username=username))
    res.set_cookie('token', token)
    return res

@app.route('/register', methods=['POST'])
def register():
    form = request.form
    required = ['username', 'password', 'email']
    for key in required:
        if not key in form:
            return jsonify(code=PARAMETER_ERROR)

    username = form['username']
    password = form['password']
    email = form['email']

    res = send_verify_email(username, password, email)

    return jsonify(code=res)

@app.route('/verify/<code>', methods=['GET'])
def verify(code):
    username, password, email = check_verify(code)

    if username != None:
        add_user(username, password, email)

    res = make_response(render_template('index.html', register_success=True))
    _, token = check_login(email, password)
    res.set_cookie('token', token)
    return res

@app.route('/login', methods=['POST'])
def login():
    form = request.form
    required = ['email', 'password']
    for key in required:
        if not key in form:
            return jsonify(code=PARAMETER_ERROR)

    email = form['email']
    password = form['password']

    status, token = check_login(email, password)
    #add cookie
    if status == SUCCESS:
        res = make_response(jsonify(code=status))
        res.set_cookie('token', token)
        return res
    else:
        return jsonify(code=PASSWORD_ERROR)

@app.route('/get_team', methods=['GET'])
def get_status():
    cookies = request.cookies
    if not 'token' in cookies:
        return jsonify(code=TOKEN_NOT_EXIST)
    token = cookies['token']
    status, uid = token2uid(token)
    if status == False:
        return jsonify(code=TOKEN_NOT_EXIST)

    status, teamname, members = uid2team(uid)
    if status != SUCCESS:
        return jsonify(code=status)
    else:
        return jsonify(code=status, teamname=teamname, members=members)

@app.route('/update_team', methods=['POST'])
def update_team():
    cookies = request.cookies
    if not 'token' in cookies:
        return jsonify(code=TOKEN_NOT_EXIST)
    token = cookies['token']
    status, uid = token2uid(token)
    if status == False:
        return jsonify(code=TOKEN_NOT_EXIST)

    form = request.form
    required = ['teamname', 'caption-name', 'caption-email', 'caption-organization', 'member-num']
    for key in required:
        if not key in form:
            return jsonify(code=PARAMETER_ERROR)

    teamname = form['teamname']

    member_num = int(form['member-num'])
    members = []
    members.append({
        'name': form['caption-name'],
        'email': form['caption-email'],
        'organization': form['caption-organization']
        })
    for i in range(1, member_num):
        if not 'member%d-name'%i in form or not 'member%d-email'%i in form or not 'member%d-organization'%i in form:
            return jsonify(code=PARAMETER_ERROR)
        members.append({
            'name': form['member%d-name'%i],
            'email': form['member%d-email'%i],
            'organization': form['member%d-organization'%i]
        })

    res = update_team_by_uid(uid, teamname, members)
    return jsonify(code=res)

@app.route('/forget_password', methods=['POST'])
def forget_password():
    form = request.form
    if not 'email' in form:
        return jsonify(code=PARAMETER_ERROR)

    email = form['email']
    res = check_email_exist(email)
    if res == False:
        return jsonify(code=EMAIL_NOT_EXIST)

    send_reset_email(email)
    return jsonify(code=SUCCESS)

@app.route('/reset_password/<code>', methods=['GET'])
def reset_password(code):
    form = request.form
    if not 'password' in form:
        return jsonify(code=PARAMETER_ERROR)

    password = form['password']
    uid = code2uid(code)
    res = check_update(uid, password)
    return jsonify(code=res)

@app.route('/logout', methods=['POST'])
def logout():
    res = make_response(jsonify(code=SUCCESS))
    res.delete_cookie("token")
    return res

if __name__ == '__main__':
    app.run('0.0.0.0', 5000)