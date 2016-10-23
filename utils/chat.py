import psycopg2
import psycopg2.extensions
from profapp import create_app, load_database
import socketio, eventlet
import re, time, datetime
from profapp.models.messenger import Contact, Message
from profapp.controllers.errors import BadDataProvided
from flask import g
from utils import db_utils

# conn = psycopg2.connect(dbname=Config.database, user=Config.username, password=Config.password,
#                         host=Config.host)
# conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
# conn.autocommit = True
# curs = conn.cursor()

connected_sid_user_id_chatroom_id = {}
connected_user_id_sids = {}
connected_chatroom_id_sids = {}


class controlled_execution:
    def __enter__(self):
        ctx.push()
        return True

    def __exit__(self, type, value, traceback):
        g.db.commit()
        ctx.pop()


app = create_app(apptype='profi')
ctx = app.app_context()

with controlled_execution():
    load_database(app.config['SQLALCHEMY_DATABASE_URI'])()

sio = socketio.Server(cookie='prsio')


def append_create(dict, index, value):
    if not index:
        return None

    if index not in dict:
        dict[index] = []

    if value not in dict[index]:
        dict[index].append(value)


def remove_delete(dict, index, value):
    if not index or index not in dict:
        return None

    dict[index].remove(value)
    if len(dict[index]) == 0:
        del dict[index]


def check_user_id(environ):
    session_id = environ.get('HTTP_COOKIE', None)
    if not session_id:
        return False
    session_id = re.sub(r'^(.*;\s*)?beaker\.session\.id=([0-9a-f]*).*$', r'\2', session_id)
    import memcache
    mc = memcache.Client(['memcached.profi:11211'], debug=0)
    session = mc.get(session_id + '_session')
    return session.get('user_id', False) if session else False


@sio.on('connect')
def connect(sid, environ):
    user_id = check_user_id(environ)
    print('connect', user_id)
    if not user_id:
        return False

    connected_sid_user_id_chatroom_id[sid] = [user_id, None]
    append_create(connected_user_id_sids, user_id, sid)


@sio.on('select_chat_room_id')
def select_chat_room(sid, message):
    with controlled_execution():
        print('chat room selected', message['select_chat_room_id'])
        connected_sid_user_id_chatroom_id[sid][1] = message['select_chat_room_id']
        if message['select_chat_room_id']:
            contact = Contact.get(message['select_chat_room_id'])
        append_create(connected_chatroom_id_sids, message['select_chat_room_id'], sid)


@sio.on('disconnect')
def disconnect(sid):
    [user_id, chatroom_id] = connected_sid_user_id_chatroom_id[sid]
    print('disconnect', sid, user_id, chatroom_id)
    remove_delete(connected_user_id_sids, user_id, sid)
    remove_delete(connected_chatroom_id_sids, chatroom_id, sid)
    del connected_sid_user_id_chatroom_id[sid]


def notify_unread(user_id, chatroom_ids = []):
    to_send = {'total': int(
        float(db_utils.execute_function("message_unread_count('%s', NULL)" % (user_id,))))}
    for chatroom_id in chatroom_ids:
        to_send[chatroom_id] = int(float(
            db_utils.execute_function("message_unread_count('%s', '%s')" % (user_id, chatroom_id))))
    if user_id in connected_user_id_sids:
        for sid_for_another_user in connected_user_id_sids[user_id]:
            sio.emit('set_unread_message_count', to_send, sid_for_another_user)

@sio.on('send_message')
def send_message(sid, message_text):
    with controlled_execution():
        [user_id, chatroom_id] = connected_sid_user_id_chatroom_id[sid]
        contact = Contact.get(chatroom_id)

        message = Message(contact_id=contact.id, content=message_text, from_user_id=user_id)
        message.save()
        message = Message.get(message.id)

        another_user_to_notify_unread = contact.user1_id if contact.user2_id == user_id else contact.user2_id
        if chatroom_id in connected_chatroom_id_sids:
            for sid_for_this_chat_room in connected_chatroom_id_sids[chatroom_id]:
                if connected_sid_user_id_chatroom_id[sid_for_this_chat_room][0] == another_user_to_notify_unread:
                    another_user_to_notify_unread = None
                    print("SELECT message_set_read('%s', ARRAY ['%s']);" % (contact.id, message.id))
                    g.db().execute("SELECT message_set_read('%s', ARRAY ['%s']);" % (contact.id, message.id))
                    break

        message_tosend = message.client_message()

        for sid_for_this_chat_room in connected_chatroom_id_sids[chatroom_id]:
            sio.emit('new_message', message_tosend, sid_for_this_chat_room)

        if another_user_to_notify_unread:
            notify_unread(another_user_to_notify_unread, [chatroom_id])

        return {'ok': True, 'message_id': message.id}

@sio.on('load_messages')
def send_message(sid, message):
    with controlled_execution():
        [user_id, chatroom_id] = connected_sid_user_id_chatroom_id[sid]
        contact = Contact.get(message['chat_room_id'])
        older = message.get('older', False)
        ret = contact.get_messages(user_id, 50, older, message.get('first_message_id' if older else 'last_message_id', None))

        read_ids = [m.id for m in ret['messages'] if m.from_user_id != user_id and not m.read_tm]
        if len(read_ids):
            g.db().execute("SELECT message_set_read('%s', ARRAY ['%s']);" % (contact.id, "', '".join(read_ids)))
            notify_unread(user_id, [chatroom_id])

        ret['messages'] = [m.client_message() for m in ret['messages']]

        return ret


# def notify_unread(user_id, contact_id):
#     print('notify_unread', user_id, contact_id)
#     if len(get_sids_in_room('user-' + user_id)):
#         curs.execute("SELECT message_unread_count('%s', NULL)" % (user_id,))
#         tosend = {'total': int(float(curs.fetchone()[0]))}
#         if contact_id:
#             curs.execute("SELECT message_unread_count('%s', '%s')" % (user_id, contact_id))
#             tosend[contact_id] = int(float(curs.fetchone()[0]))
#         sio.emit('set_unread_message_count', tosend, 'user-' + user_id)


# def new_message_old(to_user_id, message):
#     import time
#     import datetime
#     import random
#     # if random.randint(0,10) > 5:
#     #     raise AssertionError('hello')
#
#
#
#     contact_id = message['contact_id']
#     message_tosend = {'id': message['id'],
#                       'content': message['content'],
#                       'from_user_id': message['from_user_id'],
#                       'cr_tm': message['cr_tm'],
#                       'timestamp': time.mktime(
#                           datetime.datetime.strptime(message['cr_tm'], "%Y-%m-%dT%H:%M:%S.%f").timetuple()),
#                       }
#
#     no_adresee_listen = True
#     for sid_in_chat_room in get_sids_in_room('chat-room-' + contact_id):
#         for room_name in sio.manager.get_rooms(sid_in_chat_room, '/'):
#             if room_name == 'user-' + to_user_id:
#                 no_adresee_listen = False
#                 sio.emit(event='new_message', data={'message': message_tosend, 'chat_room_id': contact_id},
#                          room=sid_in_chat_room)
#
#     if no_adresee_listen:
#         curs.execute("SELECT message_notify_unread('%s', '%s');" % (to_user_id, contact_id))
#     else:
#         curs.execute("SELECT message_set_read('%s', '%s', ARRAY ['%s']);" %
#                      (to_user_id, contact_id, "', '".join([message['id']])))


# def dblisten():
#     from eventlet.hubs import trampoline
#     """
#     Open a db connection and add notifications to *q*.
#     """
#     while True:
#         trampoline(conn, read=True)
#         conn.poll()
#         while conn.notifies:
#             notify = conn.notifies.pop(0)
#             print("Got NOTIFY:", notify.pid, notify.channel, notify.payload)
#             (messagetype, message_info_id) = tuple(notify.channel.split('___'))
#
#             if messagetype == 'new_message_to_user':
#                 new_message(message_info_id.replace('_', '-'), json.loads(notify.payload))
#             elif messagetype == 'message_unread_count':
#                 notify_unread(message_info_id.replace('_', '-'), notify.payload)


# thread = eventlet.spawn(dblisten)

app = socketio.Middleware(sio, app)
eventlet.wsgi.server(eventlet.listen(('', 5000)), app)
