import time

import paho.mqtt.client as mqtt

client: mqtt.Client = None


def loop():
    c = 0
    while True:
        client.publish('test', c + 1, 0)
        c += 1
        print(c)
        time.sleep(.1)


def on_message(client, userdata, message):
    print(message)


def run():
    global client
    client = mqtt.Client()
    client.on_message = on_message

    client.connect('localhost', 1883)
    loop()


if __name__ == '__main__':
    run()
