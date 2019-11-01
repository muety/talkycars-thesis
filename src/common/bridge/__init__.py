import logging
from multiprocessing.pool import ThreadPool
from threading import Thread, Lock
from typing import Tuple, Callable, Set

import paho.mqtt.client as mqtt

from common.constants import MQTT_QOS


class MqttBridge:
    def __init__(
            self,
            broker_host: str = 'localhost',
            broker_port: int = 1883,
            client_id: str = '',
            discard_when_busy: bool = False,
            on_connect: Callable = None,
            on_disconnect: Callable = None
    ):
        self.broker_config: Tuple[str, int] = (broker_host, broker_port,)
        self.client: mqtt.Client = mqtt.Client(client_id=client_id)
        self.discard_when_busy: bool = discard_when_busy
        self.subscriptions: Set[str] = set()
        self.loop_thread: Thread = None
        self.read_pool: ThreadPool = ThreadPool(processes=1)
        self.in_lock: Lock = Lock()

        self.connected: bool = False
        self.cb = {
            'connect': on_connect,
            'disconnect': on_disconnect,
        }

        self.client.on_connect = self._on_connect

    def __del__(self):
        self.disconnect()

    def listen(self, block=True):
        self.client.connect(*self.broker_config[:2])

        try:
            if block:
                self.client.loop_forever()
            else:
                self.loop_thread = Thread(target=self.client.loop_forever, daemon=True)
                self.loop_thread.start()
        except:
            self.disconnect()

    def subscribe(self, topic: str, callback: Callable):
        if topic not in self.subscriptions:
            self.client.subscribe(topic, qos=MQTT_QOS)
            self.subscriptions.add(topic)
            self.client.message_callback_add(topic, self.wrap_callback(callback))

    def unsubscribe(self, topic: str, callback: Callable):
        if topic not in self.subscriptions:
            return
        self.subscriptions.remove(topic)
        self.client.message_callback_remove(topic)

    def publish(self, topic: str, message: bytes):
        self.client.publish(topic, message, qos=MQTT_QOS)

    def disconnect(self):
        self.client.disconnect()
        self.loop_thread = None

        self.connected = False
        if self.cb['disconnect']:
            self.cb['disconnect']()

        logging.info('Disconnected from broker.')

    def _on_connect(self, client, userdata, flags, rc):
        logging.info(f'Connected to {self.broker_config} with result code {str(rc)}.')

        self.connected = True
        if self.cb['connect']:
            self.cb['connect']()

        for topic in self.subscriptions:
            client.subscribe(topic, qos=MQTT_QOS)

    def wrap_callback(self, callback: Callable) -> Callable:
        def cb(client, userdata, msg):
            with self.in_lock:
                callback(msg.payload)

        def on_message(*args):
            if self.discard_when_busy and self.in_lock.locked():
                return

            self.read_pool.apply_async(cb, args=args)

        return on_message


class MqttBridgeUtils:
    pass
