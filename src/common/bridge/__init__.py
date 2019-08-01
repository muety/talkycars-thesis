import logging
from threading import Thread
from typing import Tuple, Callable, Dict, Set

import paho.mqtt.client as mqtt


class MqttBridge:
    def __init__(self, broker_host: str = 'localhost', broker_port: int = 1883):
        self.broker_config: Tuple[str, int] = (broker_host, broker_port,)
        self.client: mqtt.Client = mqtt.Client()
        self.subscriptions: Dict[str, Set[Callable]] = {}
        self.loop_thread: Thread = None
        self.connected: bool = False

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def listen(self, block=True):
        self.client.connect(*self.broker_config[:2])

        try:
            if block:
                self.client.loop_forever()
            else:
                self.loop_thread = Thread(target=self.client.loop_forever)
                self.loop_thread.start()
        except:
            self.tear_down()

    def subscribe(self, topic: str, callback: Callable):
        if topic not in self.subscriptions:
            self.subscriptions[topic] = set()
            self.client.subscribe(topic)

        self.subscriptions[topic].add(callback)

    def unsubscribe(self, topic: str, callback: Callable):
        if topic not in self.subscriptions:
            return

        self.subscriptions[topic].remove(callback)

    def publish(self, topic: str, message: bytes):
        self.client.publish(topic, message)

    def tear_down(self):
        self.client.disconnect()
        self.loop_thread = None
        self.connected = False
        logging.info('Disconnected from broker.')

    def _on_connect(self, client, userdata, flags, rc):
        logging.info(f'Connected to {self.broker_config} with result code {str(rc)}.')

        self.connected = True

        for topic in frozenset(self.subscriptions.keys()):
            client.subscribe(topic)

    def _on_message(self, client, userdata, msg):
        # TODO: Optimize !
        matching_subs = [s[1] for s in self.subscriptions.items() if mqtt.topic_matches_sub(s[0], msg.topic)]
        if len(matching_subs) == 0:
            return

        for s in set().union(*matching_subs):
            s(msg.payload)


class MqttBridgeUtils:
    pass
