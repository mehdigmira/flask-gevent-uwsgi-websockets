# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division

import json

from flask import request
from flask.ext.restful import Resource
from gevent.event import Event
from gevent.queue import Queue, Empty
from gevent.select import select
from gevent import wait, spawn
try:
    import uwsgi
except ImportError:
    uwsgi = None
else:
    _websocket_fd = uwsgi.connection_fd()

    _websocket_send_event = Event()
    _websocket_recv_event = Event()
    _websocket_disconnect_event = Event()

    _websocket_send_queue = Queue()
    _websocket_recv_queue = Queue()
    _websocket_disconnect_queue = Queue()

    _websocket_handlers = {'_websocket_listen': None}


def listen():
    while True:
        select([_websocket_fd], [], [])  # select fd
        print("set recv")
        _websocket_recv_event.set()


def start_websocket():
    assert request.headers.get('Upgrade') == "websocket", "/websockets is only available for websocket protocol"
    assert uwsgi is not None, "You must run your app using uwsgi if you want to use the /websockets route"
    env = request.headers.environ
    uwsgi.websocket_handshake(env['HTTP_SEC_WEBSOCKET_KEY'], env.get('HTTP_ORIGIN', ''))  # engage in websocket

    _websocket_handlers['_websocket_listen'] = spawn(listen)  # Spawn greenlet that will listen to fd


def add_websockets_route(app):
    app.add_url_rule('/websockets', 'websockets', start_websocket)






:# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division

import json

from flask import request
from flask.ext.restful import Resource
from gevent.event import Event
from gevent.queue import Queue, Empty
from gevent.select import select
from gevent import wait, spawn

from ..utils import cayzn_verify_jwt

try:
    import uwsgi
except ImportError:
    pass


class CayznWebsocketHandler:
    def __init__(self):
        self.message_queue = Queue()
        self.hub = None
        self.greenlet = None

    def run(self):
        raise Exception("run method must be overridden")

    def send(self, msg):
        self.hub.send_queue.put(msg)
        self.hub.send.set()

    def get(self):
        return self.message_queue.get()

    def spawn(self):
        self.greenlet = spawn(self.run, self)

    def kill(self):
        self.greenlet.kill()


def ws_handler(func):
    handler = CayznWebsocketHandler()
    handler.run = func
    return handler


class CayznWebsocket(Resource):
    # To access this end point, frontend should do smth like:
    # ws = new WebSocket('wss://idtgv.cayzn.com/websockets/<jwt token>')
    verify_jwt = False  # Websocket doesn't allow Auth header
    allowed_access_levels = ['yield.cayzn.com']

    # TODO: Maybe add a layer of abstraction in the way we use websockets, once the workflow is clear enough
    # TODO: If we upgrade to celery 4 (06 July 2016: not yet released), use Redis PUBSUB rather than polling
    def get(self, token):
        assert request.headers.get('Upgrade') == "websocket", "/websockets is only available for websocket protocol"

        request.headers.environ['HTTP_AUTHORIZATION'] = 'Bearer ' + token  # pretend the token was in the headers
        # cayzn_verify_jwt(allowed_access_levels=self.allowed_access_levels)

        env = request.headers.environ
        uwsgi.websocket_handshake(env['HTTP_SEC_WEBSOCKET_KEY'], env.get('HTTP_ORIGIN', ''))  # engage in websocket

        self.websocket_fd = uwsgi.connection_fd()

        self.send = Event()  # If a handler needs to post a message to the websocket, it will set this event
        self.disconnect = Event()  # If a handler has finished, it will set this event
        self.received = Event()  # If a msg was received, this event is set

        self.send_queue = Queue()
        self.disconnect_queue = Queue()

        self.handlers = {}  # all handlers that are active

        self.g_listen = spawn(self.listen)  # Spawn greenlet that will listen to fd

        #  If user disconnected, return
        # elif message received, handle it
        while True:
            ready = wait([self.send, self.disconnect, self.received], None, 1)  # wait for events with a 3s timeout
            if ready:  # an event was set
                if ready[0] == self.received:
                    msg = uwsgi.websocket_recv_nb()
                    print msg
                    if msg:
                        json_msg = json.loads(msg)
                        if json_msg['namespace'] == "celery":
                            if "celery" not in self.handlers:
                                celery_task_status = celery_task_status

                                self.handlers["celery"] = celery_task_status
                                celery_task_status.spawn()
                            self.handlers["celery"].message_queue.put(json_msg['value'])
                    self.received.clear()
                elif ready[0] == self.send:  # One or more handlers requested a message to be sent
                    while True:
                        try:
                            msg = self.send_queue.get_nowait()
                        except Empty:
                            break
                        uwsgi.websocket_send(msg)
                    self.send.clear()
                elif ready[0] == self.disconnect:  # One or more handlers finished
                    while True:
                        try:
                            disconnect_handler = self.disconnect_queue.get_nowait()
                        except Empty:
                            break
                        self.handlers.pop(disconnect_handler)
                    self.disconnect.clear()

    def kill_all(self):
        self.g_listen.kill()
        for handler in self.handlers.values():
            handler.kill()

    def listen(self):
        while True:
            select([self.websocket_fd], [], [])  # select fd
            print("set recv")
            self.received.set()


@ws_handler
def celery_task_status(ws):
    while True:
        msg = ws.get()
        ws.send(msg)
