# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division

import json

from flask import request
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


def _listen():
    while True:
        select([_websocket_fd], [], [])  # select fd
        print("set recv")
        _websocket_recv_event.set()


def _kill_all():
    for handler in _websocket_handlers.values():
        handler.kill()


def _start_websocket():
    assert request.headers.get('Upgrade') == "websocket", "/websockets is only available for websocket protocol"
    assert uwsgi is not None, "You must run your app using uwsgi if you want to use the /websockets route"
    env = request.headers.environ
    uwsgi.websocket_handshake(env['HTTP_SEC_WEBSOCKET_KEY'], env.get('HTTP_ORIGIN', ''))  # engage in websocket

    _websocket_handlers['_websocket_listen'] = spawn(_listen)  # Spawn greenlet that will listen to fd

    while True:
        ready = wait([_websocket_send_event, _websocket_recv_event, _websocket_disconnect_event], None, 1)  # wait for events
        if ready:  # an event was set
            if ready[0] == _websocket_recv_event:
                msg = uwsgi.websocket_recv_nb()
                if msg is not None:
                    json_msg = json.loads(msg)
                    if json_msg['namespace'] == "celery":
                        pass
                _websocket_recv_event.clear()
            elif ready[0] == _websocket_send_event:  # One or more handlers requested a message to be sent
                while True:
                    try:
                        msg = _websocket_recv_queue.get_nowait()
                    except Empty:
                        break
                    uwsgi.websocket_send(msg)
                _websocket_send_event.clear()
            elif ready[0] == _websocket_disconnect_event:  # One or more handlers finished
                while True:
                    try:
                        disconnect_handler = _websocket_disconnect_queue.get_nowait()
                    except Empty:
                        break
                    _websocket_handlers.pop(disconnect_handler)
                _websocket_disconnect_event.clear()


def add_websockets_route(app):
    app.add_url_rule('/websockets', 'websockets', _start_websocket)


