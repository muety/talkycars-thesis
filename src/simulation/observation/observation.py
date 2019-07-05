class Observation:
    def __init__(self, timestamp):
        assert isinstance(timestamp, int) or isinstance(timestamp, float)

        self.timestamp = timestamp