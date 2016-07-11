# flask-gevent-uwsgi-websockets
A small library that enables using high performance websockets on top of: flask, gevent, uwsgi.
The library is built to enable multiplexing over a single websocket, by using namespaces: only one websocket per browser session should be used.

You can build namespaces like this:

```python
@websocket_handler(namespace='yournamespace')
def yournamespace(ws):
    # your code here
```

ws gives you access to the websocket api:

ws.get() blocks until you get a message from the user
ws.send() sends a message to the user

For example an echo server could be written like this:

```python
@websocket_handler(namespace='echo')
def echo(ws):
    while True:
        msg = ws.get()
        if msg is not None:
            ws.send(msg)
        else:
            return
```

On the client side, your code would be something like this:

```javascript
var socket = new Websocket("ws://localhost:5000/websockets");
socket.send(JSON.stringify({
  namespace: "echo",
  value: "hola"
}));
```
