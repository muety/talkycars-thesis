import time
from multiprocessing.pool import ThreadPool
from threading import Lock

import paho.mqtt.client as mqtt

c: int = 0
client: mqtt.Client = None
lock: Lock = Lock()
receive_pool: ThreadPool = ThreadPool(processes=2)


def on_connect(client, userdata, flags, rc):
    print('Connected')
    client.subscribe('test', 0)


def on_message(*args):
    receive_pool.apply_async(handle_message, args=args)


def handle_message(client: mqtt.Client, userdata, msg):
    global c

    if lock.locked():
        return

    with lock:
        c += 1
        print(f'{c} {msg.payload}')
        time.sleep(.5)


def run():
    global client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect('localhost', 1883)
    client.loop_forever()


if __name__ == '__main__':
    run()
