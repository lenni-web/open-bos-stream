class DisplayManager:

    def __init__(self, config):

        self.config = config

    def start(self):

        if not self.config.enabled:
            return

    def stop(self):

        pass