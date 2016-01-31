from uuid import uuid4

class Packet:
    def __init__(self):
        self.id = uuid4()


class DataPacket(Packet):
    def __init__(self, payload=None):
        super().__init__()
        self.payload = payload


class CommandPacket(Packet):
    def __init__(self, command, args=None):
        super().__init__()
        self.command = command
        self.args = args

