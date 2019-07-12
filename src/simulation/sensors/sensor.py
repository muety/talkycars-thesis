from client.client import TalkyClient


class Sensor:
    def __init__(self, client: TalkyClient=None):
        self.client = client

