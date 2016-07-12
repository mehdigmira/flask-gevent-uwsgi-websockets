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

    _websocket_send_queue = Queue()

    _websocket_handlers = {'_websocket_listen': None}


def _listen(websocket_fd):
    """
    This will listen to the websocket file descriptor in a gevent-friendly way, and notify when the fd is ready

    :param websocket_fd: the websocket file descriptor
    :return:
    """
    while True:
        # select fd with a 3s timeout, so that we can ping client from time to time
        select([websocket_fd], [], [], timeout=3)
        _websocket_recv_event.set()


def _kill_all():
    """
    This will kill all spawned handlers
    :return:
    """
    for handler in _websocket_handlers.values():
        handler.kill()


def _start_websocket():
    """
    This is the most important piece of the code. It's the only one that is allowed to use the uwsgi websocket api.
    It deals with receiving:
    - spawn a _listen greenlet
    _ when notified that the websocket fd is ready, it will fetch the message, and push it to the right handler
    and writing:
    - spawns a handler whenever necessary
    - when notified that a handler wants to writes, does the writing
    :return:
    """
    assert request.headers.get('Upgrade') == "websocket", "/websockets is only available for websocket protocol"
    assert uwsgi is not None, "You must run your app using uwsgi if you want to use the /websockets route"
    env = request.headers.environ
    uwsgi.websocket_handshake(env['HTTP_SEC_WEBSOCKET_KEY'], env.get('HTTP_ORIGIN', ''))  # engage in websocket

    _websocket_handlers['_websocket_listen'] = spawn(_listen, uwsgi.connection_fd())  # Spawn greenlet that will listen to fd

    while True:
        ready = wait([_websocket_send_event, _websocket_recv_event], None, 1)  # wait for events
        if ready:  # an event was set
            if ready[0] == _websocket_recv_event:
                try:
                    msg = uwsgi.websocket_recv_nb()
                except IOError:
                    _kill_all()
                    return
                if msg:
                    json_msg = json.loads(msg)
                    handler = _websocket_handlers[json_msg['namespace']]
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


def add_websockets_route(app):
    """
    adds the websockets route to the flask app, and monkey patches the wsgi app, so that when a ws connection
    is required, flask doesn't send the http headers.
    :param app: flask app
    :return:
    """
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
    """
    the handler decorator
    :param namespace: the namespace for which you're building a handler
    :return:
    """
    def decorator(func):
        handler = _WebsocketHandler(namespace)
        try:
            _websocket_handlers[namespace] = handler
        except NameError:
            raise Exception("You must run your app using uwsgi if you want to use the /websockets route")

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
    """
    Websocket handler class. Holds some useful information, and provides a nice api
     to communicate withe the main greenlet (_start_websocket)
    """
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
