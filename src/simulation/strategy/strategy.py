class Strategy:
    def __init__(self):
        self.ego = None

    def init(self, ego):
        self.ego = ego

    def step(self, **kwargs) -> bool:
        raise NotImplementedError()

    def spawn(self):
        raise NotImplementedError()
