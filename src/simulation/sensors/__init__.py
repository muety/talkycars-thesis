from client.client import TalkyClient

class Sensor:
    def __init__(self, client: TalkyClient=None):
        self.client = client

from .camera_rgb import *
from .gnss import *
from .lidar import *