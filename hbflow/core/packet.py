

class Packet:
    def __init__(self):
        self.id = uuid4()


class DataPacket:
    def __init__(self, payload=None):
        super().__init__()
        self.payload = payload


class CommandPacket:
    def __init__(self, command):
        super().__init__(name)

