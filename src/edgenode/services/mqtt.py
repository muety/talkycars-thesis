import logging
from typing import Tuple, Callable, List, Dict

import paho.mqtt.client as mqtt


class MqttService:
    def __init__(self, broker_host='localhost', broker_port=1883):
        self.broker_config: Tuple[str, int] = (broker_host, broker_port,)
        self.client: mqtt.Client = mqtt.Client()
        self.subscriptions: Dict[str, List[Callable]] = {}

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        self.client.connect(*self.broker_config[:2])

        try:
            self.client.loop_forever()
        except:
            self.tear_down()

    def tear_down(self):
        self.client.disconnect()
        logging.info('Disconnected from broker.')

    def _on_connect(self, client, userdata, flags, rc):
        logging.info(f'Connected to {self.broker_config} with result code {str(rc)}.')

        for topic in frozenset(self.subscriptions.keys()):
            client.subscribe(topic)

    def _on_message(self, client, userdata, msg):
        if msg.topic not in self.subscriptions:
            return

        for s in self.subscriptions[msg.topic]:
            s(msg.payload)
