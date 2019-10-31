# mqtt-bench -action pub -broker tcp://localhost:1883 -clients 9 -count 10000 -size 160000 -toc test

import time
from multiprocessing.pool import ThreadPool
from threading import Lock, Thread

import paho.mqtt.client as mqtt

c: int = 0
start: float = 0
client: mqtt.Client = None
lock: Lock = Lock()
receive_pool: ThreadPool = ThreadPool(processes=2)


def on_connect(client, userdata, flags, rc):
    print('Connected')
    client.subscribe('test/#', 0)


def on_message(*args):
    global start

    if start == 0:
        print('Got first message')
        start = time.monotonic()

    receive_pool.apply_async(handle_message, args=args)


def handle_message(client: mqtt.Client, userdata, msg):
    global c

    if lock.locked():
        return

    with lock:
        if c % 100 == 0:
            print(f'[{c}] Still receiving ...')

        c += 1
        time.sleep(.01)


def monitor():
    while True:
        if start > 0:
            print(f'{c / (time.monotonic() - start)} msgs / sec')
        time.sleep(3)


def run():
    global client

    Thread(target=monitor).start()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect('localhost', 1883)
    client.loop_forever()


if __name__ == '__main__':
    run()
