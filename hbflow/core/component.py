from uuid import uuid4
from datetime import datetime
from transitions import Machine
from hbflow.utils import InstanceCounterMeta
import importlib
import logging

class GraphException(Exception):
    pass


class ComponentException(Exception):
    pass


class Graph(object, metaclass=InstanceCounterMeta):
    states = ['new', 'resolved', 'unresolved', 'running', 'idle', 'stopping', 'stopped', 'shutdown']

    def __new__(cls):
        instance = super().__new__(cls)
        instance._seq_id = next(cls._ids)
        instance.name = cls.__name__ + "_" + str(instance._seq_id)
        instance.logger = logging.getLogger(__name__)
        return instance

    def __init__(self, name=None, description=None, author=None, date=datetime.now()):
        if name:
            self.name = name
        self.description = description
        self.author = author
        self.date = date
        self.id = uuid4()
        self.processes = dict()

    def add_process(self, name, component_name, group=None):
        if name in self.processes:
            raise Graph("Duplicate process name '%s'" % name)
        self.processes[name] = new_component_instance(component_name, name)
        # To be removed
        if group:
            self.logger.warning("Process not implemented yet. Adding '%s' process to root" % name)

    @staticmethod
    def init_from_dictionary(dict_spec: dict):
        # Allow 'graph' as optional root
        if 'graph' in dict_spec:
            graph_config = dict_spec.get('graph')
        else:
            graph_config = dict_spec

        name = graph_config.get('name', None)
        description = graph_config.get('description', None)
        author = graph_config.get('author', None)
        date = graph_config.get('date', None)
        graph = Graph(name, description, author, date)

        processes = graph_config.get('processes', dict())
        for process in processes:
            component_name = process[process].get('component')
            graph.add_process(process, component_name)


def new_component_instance(component_name, name):
    """
    Create a component instance (a process) given a component name.
    The component name (formed module.class) is used to import the python module containing the class. A new class
    instance is then created with the given name.
    :param component_name: component name to load (in the form of module_name.class_name)
    :param name: optional name to give to the process
    :return: the component instance (the process)
    """
    try:
        module_name, class_name = component_name.rsplit(".", 1)
        component_class = getattr(importlib.import_module(module_name), class_name)
    except ValueError:
        raise ComponentException("Invalid component format name '%s'" % component_name)
    except AttributeError:
        raise ComponentException("Component '%s' not found in module '%s'" % (class_name, module_name))
    except ImportError:
        raise ComponentException("Module '%s' can't be imported" % module_name)

    return component_class(name) or None


class Connection(object, metaclass=InstanceCounterMeta):
    def __new__(cls):
        instance = super().__new__(cls)
        instance._seq_id = next(cls._ids)
        instance.name = cls.__name__ + "_" + str(instance._seq_id)
        return instance

    def __init__(self, name=None):
        if name:
            self.name = name


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
class Component(object, metaclass=InstanceCounterMeta):
    states = ['new', 'ready', 'waiting', 'running', 'idle', 'stopping', 'stopped', 'shutdown']
    transitions = [
        {'trigger': 'initialize', 'source': 'new', 'dest': 'ready'},
        {'trigger': 'start', 'source': 'ready', 'dest': 'idle'},
        {'trigger': 'run', 'source': ['idle', 'waiting'], 'dest': 'running'},
        {'trigger': 'wait', 'source': 'running', 'dest': 'waiting'},
        {'trigger': 'idle', 'source': 'running', 'dest': 'idle'},
        {'trigger': 'stop', 'source': ['running', 'waiting'], 'dest': 'stopping'},
        {'trigger': 'stop', 'source': 'stopping', 'dest': 'stopped'},
        {'trigger': 'shutdown', 'source': 'stopped', 'dest': 'sshutdown'},
    ]

    _in_port_defs = dict()
    _out_port_defs = dict()

    def __new__(cls):
        instance = super().__new__(cls)
        instance._seq_id = next(cls._ids)
        instance.name = cls.__name__ + "_" + str(instance._seq_id)

        for port_name in cls._in_port_defs:
            (description, display_name, array_size) = cls._in_port_defs[port_name]
            setattr(instance, port_name, InPort(description, display_name, array_size))
        for port_name in cls._out_port_defs:
            (description, display_name, array_size) = cls._out_port_defs[port_name]
            setattr(instance, port_name, OutPort(description, display_name, array_size))
        return instance

    def __init__(self, name=None):
        self.machine = Machine(model=self, states=Component.states, transitions=Component.transitions, initial='new')
        self.id = uuid4()
        if name:
            self.name = name


class Port:
    def __init__(self, description='', display_name='', array_size=1):
        self.description = description
        self.display_name = display_name
        self.array_size = array_size


class InPort(Port):
    pass


class OutPort(Port):
    pass
