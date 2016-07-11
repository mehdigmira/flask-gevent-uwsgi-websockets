from flask import Flask
from flask.ext.gevent_uwsgi_websockets import add_websockets_route, websocket_handler

app = Flask(__name__)
app = add_websockets_route(app)


@websocket_handler(name='echo')
def echo(ws):
    while True:
        msg = ws.get()
        if msg is not None:
            ws.send(msg)
        else:
            return

if __name__ == '__main__':
    app.run(debug=True, gevent=100)
