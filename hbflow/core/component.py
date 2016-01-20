from uuid import uuid4
from transitions import Machine
from hbflow.utils import InstanceCounterMeta
import importlib


class ComponentException(Exception):
    pass


class Port:
    def __init__(self, description=None, display_name=None, array_size=1):
        self.description = description
        self.display_name = display_name
        self.array_size = array_size
        self.connections = []
        for i in range(self.array_size):
            self.connections.append([])

    def add_connection(self, connection, index=0):
        self.connections[index].append(connection)

    def remove_connection(self, connection, index=0):
        self.connections[index].remove(connection)


class InputPort(Port):
    pass


class OutputPort(Port):
    pass


def new_component_instance(component, name):
    """
    Create a component instance (a process) given a component name.
    The component name (formed module.class) is used to import the python module containing the class. A new class
    instance is then created with the given name.
    :param component: component name to load (in the form of module_name.class_name)
    :param name: optional name to give to the process
    :return: the component instance (the process)
    """
    if issubclass(component, Component):
        component_class = component
    else:
        try:
            module_name, class_name = component.rsplit(".", 1)
            component_class = getattr(importlib.import_module(module_name), class_name)
        except ValueError:
            raise ComponentException("Invalid component format name '%s'" % component)
        except AttributeError:
            raise ComponentException("Component '%s' not found in module '%s'" % (class_name, module_name))
        except ImportError:
            raise ComponentException("Module '%s' can't be imported" % module_name)

    return new_process(name, component_class)


def new_process(name, component_class):
    """
    Create a process from a component class
    :param name: name of the process instance
    :param component_class: class to use as process component
    :return: the process instance
    """
    return component_class(name) or None


class Connection(object, metaclass=InstanceCounterMeta):
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._seq_id = next(cls._ids)
        instance.name = cls.__name__ + "_" + str(instance._seq_id)
        return instance

    def __init__(self, name=None):
        self.id = uuid4()
        if name:
            self.name = name

    def __eq__(self, other):
        return self.id == other.id

    def link(self, source: OutputPort, target:InputPort):
        source.add_connection(self)
        target.add_connection(self)

    def unlink(self):
        pass


class IN:
    def __init__(self, description=None, display_name=None, array_size=1):
        self.description = description
        self.display_name = display_name
        self.array_size = array_size


class OUT:
    def __init__(self, description=None, display_name=None, array_size=1):
        self.description = description
        self.display_name = display_name
        self.array_size = array_size


class Component(object, metaclass=InstanceCounterMeta):
    states = ['new', 'starting', 'waiting', 'running', 'idle', 'stopping', 'stopped', 'shutdown']
    transitions = [
        {'trigger': 'start', 'source': 'new', 'dest': 'starting'},
        {'trigger': 'start_ok', 'source': 'starting', 'dest': 'idle'},
        {'trigger': 'start_ko', 'source': 'starting', 'dest': 'stopped'},
        {'trigger': 'run', 'source': ['idle', 'waiting'], 'dest': 'running'},
        {'trigger': 'wait', 'source': 'running', 'dest': 'waiting'},
        {'trigger': 'idle', 'source': 'running', 'dest': 'idle'},
        {'trigger': 'stop', 'source': ['running', 'waiting'], 'dest': 'stopping'},
        {'trigger': 'stop', 'source': 'stopping', 'dest': 'stopped'},
        {'trigger': 'shutdown', 'source': 'stopped', 'dest': 'sshutdown'},
    ]

    _log_out = IN()
    _command_in = IN()
    _status_out = OUT()

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._seq_id = next(cls._ids)
        instance.name = cls.__name__ + "_" + str(instance._seq_id)

        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, IN):
                setattr(instance, attr_name, InputPort(attr.description, attr.display_name, attr.array_size))
            elif isinstance(attr, OUT):
                setattr(instance, attr_name, OutputPort(attr.description, attr.display_name, attr.array_size))

        return instance

    def __init__(self, name=None):
        self.machine = Machine(model=self, states=Component.states, transitions=Component.transitions, initial='new')
        self.id = uuid4()
        if name:
            self.name = name

    def input_port(self, port_name):
        return getattr(self, port_name, None)

    def output_port(self, port_name):
        return getattr(self, port_name, None)


class TestComponent(Component):
    _in = IN()
    _out = OUT()

    def __init__(self, name=None):
        super().__init__(name)
