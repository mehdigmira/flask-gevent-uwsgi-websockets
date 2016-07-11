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

    _websocket_send_event = Event()
    _websocket_recv_event = Event()
    _websocket_disconnect_event = Event()

    _websocket_send_queue = Queue()
    _websocket_recv_queue = Queue()
    _websocket_disconnect_queue = Queue()

    _websocket_handlers = {'_websocket_listen': None}


def _listen(websocket_fd):
    while True:
        select([websocket_fd], [], [])  # select fd
        print 'recv'
        _websocket_recv_event.set()


def _kill_all():
    for handler in _websocket_handlers.values():
        handler.kill()


def _start_websocket():
    assert request.headers.get('Upgrade') == "websocket", "/websockets is only available for websocket protocol"
    assert uwsgi is not None, "You must run your app using uwsgi if you want to use the /websockets route"
    env = request.headers.environ
    uwsgi.websocket_handshake(env['HTTP_SEC_WEBSOCKET_KEY'], env.get('HTTP_ORIGIN', ''))  # engage in websocket

    _websocket_handlers['_websocket_listen'] = spawn(_listen, uwsgi.connection_fd())  # Spawn greenlet that will listen to fd

    import sys
    sys.path.append('/home/mehdi/pycharm-5.0.5/debug-eggs/pycharm-debug.egg')
    import pydevd as pydevd
    pydevd.settrace('localhost', port=8000, stdoutToServer=True, stderrToServer=True)


    while True:
        ready = wait([_websocket_send_event, _websocket_recv_event, _websocket_disconnect_event], None, 1)  # wait for events
        if ready:  # an event was set
            if ready[0] == _websocket_recv_event:
                msg = uwsgi.websocket_recv_nb()
                if msg is not None:
                    print msg
                    json_msg = json.loads(msg)
                    handler = _websocket_handlers[json_msg['namespacespace']]
                    handler.go(json_msg)
                _websocket_recv_event.clear()
            elif ready[0] == _websocket_send_event:  # One or more handlers requested a message to be sent
                while True:
                    try:
                        msg = _websocket_send_queue.get_nowait()
                    except Empty:
                        break
                    uwsgi.websocket_send(json.dumps(msg))
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

    def patch_app_for_websockets(app):
        def fake_start_response(*args):
            pass

        def application(environ, start_response):
            # user wants a websocket connection, do not send the usual http headers
            if environ['HTTP_UPGRADE'] == 'websocket':
                return app(environ, fake_start_response)
            return app(environ, start_response)

        return application

    app.wsgi_app = patch_app_for_websockets(app.wsgi_app)

    return app


def websocket_handler(namespace):
    def decorator(func):
        handler = _WebsocketHandler(namespace)
        _websocket_handlers[namespace] = handler
        def run_func(*args):
            handler.is_running = True
            try:
                func(*args)
            except:
                raise
            finally:
                handler.is_running = False
        handler.run = run_func
        return handler
    return decorator


class _WebsocketHandler:
    def __init__(self, namespace):
        self.namespace = namespace
        self.message_queue = Queue()
        self.run = None
        self.greenlet = None
        self.is_running = False

    def spawn(self):
        self.greenlet = spawn(self.run, self)

    def get(self):
        return self.message_queue.get()

    def send(self, msg):
        _websocket_send_queue.put(msg)
        _websocket_send_event.set()

    def go(self, msg):
        self.message_queue.put(msg)
        if not self.is_running:
            self.spawn()

    def kill(self):
        if self.is_running:
            self.greenlet.kill()

    def run(self, *args, **kwargs):
        raise Exception("run method in WebsocketHandler must be overridden")
