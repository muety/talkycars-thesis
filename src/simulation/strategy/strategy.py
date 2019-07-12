class Strategy:
    def __init__(self):
        self.subject = None

    def init(self, subject):
        self.subject = subject

    def step(self, **kwargs) -> bool:
        raise NotImplementedError()

    def spawn(self):
        raise NotImplementedError()
