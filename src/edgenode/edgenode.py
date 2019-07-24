from .services import MqttService, logging


def run():
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

    mqtt = MqttService()
