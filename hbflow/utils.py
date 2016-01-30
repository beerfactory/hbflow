import itertools


class InstanceCounterMeta(type):
    """ Metaclass to make instance counter not share count with descendants
    """
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        cls._ids = itertools.count(1)


class IdentifiableObject(object, metaclass=InstanceCounterMeta):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seq_id = next(self.__class__._ids)
        self._instance_name = self.__class__.__name__ + "_" + str(self._seq_id)
