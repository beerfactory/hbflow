from uuid import uuid4
from datetime import datetime
from hbflow.utils import InstanceCounterMeta


class GraphException(Exception):
    pass


class Graph(object, metaclass=InstanceCounterMeta):
    def __new__(cls):
        instance = super().__new__(cls)
        instance._seq_id = next(cls._ids)
        return instance

    def __init__(self, name=None, description=None, author=None, date=datetime.now()):
        if not name:
            self.name = "Graph_" + str(self._seq_id)
        else:
            self.name = name
        self.description = description
        self.author = author
        self.date = date
        self.id = uuid4()

    @classmethod
    def create_from_dictionary(cls, dict_spec: dict):
        # Allow 'graph' as optional root
        if 'graph' in dict_spec:
            graph_config = dict_spec.get('graph')
        else:
            graph_config = dict_spec

        name = graph_config.get('name', None)
        description = graph_config.get('description', None)
        author = graph_config.get('author', None)
        date = graph_config.get('date', None)
        graph = cls(name, description, author, date, graph)
        return graph


def IN(name, description=None, display_name=None, array_size=1):
    def wrapper(cls):
        if not hasattr(cls, '_in_port_defs'):
            raise TypeError("class '%s' incompatible with IN decorator" % cls.__name__)
        if name in cls._in_port_defs:
            raise ValueError("IN port '%s' already exists" % name)

        cls._in_port_defs[name] = (description, display_name, array_size)
        return cls
    return wrapper


def OUT(cls, name, *args, **kwargs):
    if not hasattr(cls, '_out_port_defs'):
        raise TypeError("class '%s' incompatible with OUT decorator" % cls.__name__)
    if name in cls._out_port_defs:
        raise ValueError("OUT port '%s' already exists" % name)

    description = kwargs.get('description', None)
    display_name = kwargs.get('display_name', None)
    array_size = kwargs.get('array_size', 1)
    cls._out_port_defs[name] = (description, display_name, array_size)


@IN(name="debug")
class Component:
    _in_port_defs = dict()
    _out_port_defs = dict()

    def __new__(cls):
        instance = super().__new__(cls)
        for port_name in cls._in_port_defs:
            (description, display_name, array_size) = cls._in_port_defs[port_name]
            setattr(instance, port_name, InPort(description, display_name, array_size))
        for port_name in cls._out_port_defs:
            (description, display_name, array_size) = cls._out_port_defs[port_name]
            setattr(instance, port_name, OutPort(description, display_name, array_size))
        return instance

    def __init__(self):
        self.id = uuid4()


class Port:
    def __init__(self, description='', display_name='', array_size=1):
        self.description = description
        self.display_name = display_name
        self.array_size = array_size


class InPort(Port):
    pass


class OutPort(Port):
    pass
