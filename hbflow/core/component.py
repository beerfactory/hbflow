import logging
from uuid import uuid4
from transitions import Machine
from hbflow.utils import InstanceCounterMeta, IdentifiableObject
import importlib


class ComponentException(Exception):
    pass


class Port(IdentifiableObject):
    def __init__(self, name, component, description=None, display_name=None, array_size=1):
        super().__init__()
        if name:
            self.name = name
        else:
            self.name = self._instance_name
        self.component = component
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class OutputPort(Port):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


def get_component_class(component_name):
    """
    Find a component given its component name.
    The component name (formed module.class) is used to import the python module containing the class. A new class
    instance is then created with the given name.
    :param component_name: component name to load (in the form of module_name.class_name)
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
    return component_class


class Connection(IdentifiableObject):
    states = ['new', 'linked', 'unlinked']

    def __init__(self, name=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.id = uuid4()
        self.machine = Machine(model=self, states=Connection.states, initial='new')
        if name:
            self.name = name
        else:
            self.name = self._instance_name
        self.source = None
        self.target = None

    def __eq__(self, other):
        return self.id == other.id

    def link(self, source: OutputPort, target: InputPort):
        self.source = source
        self.target = target
        source.add_connection(self)
        target.add_connection(self)
        self.logger.debug("Linked created: %s:%s -> %s:%s" % (source.component.name, source.name, target.component.name, target.name))
        self.to_linked()

    def unlink(self):
        self.source = None
        self.target = None
        # Todo: remove connection from source and target
        self.to_unlinked()


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


class Component(IdentifiableObject):
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
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, IN):
                setattr(instance, attr_name, InputPort(attr_name, instance, attr.description, attr.display_name, attr.array_size))
            elif isinstance(attr, OUT):
                setattr(instance, attr_name, OutputPort(attr_name, instance, attr.description, attr.display_name, attr.array_size))
        return instance

    def __init__(self, name=None):
        super().__init__()
        self.machine = Machine(model=self, states=Component.states, transitions=Component.transitions, initial='new')
        self.id = uuid4()
        if name:
            self.name = name
        else:
            self.name = self._instance_name

    def input_port(self, port_name):
        return getattr(self, port_name, None)

    def output_port(self, port_name):
        return getattr(self, port_name, None)


def new_component_instance(component, name) -> Component:
    """
    Create a component instance (a process) given a component name.
    The component name (formed module.class) is used to import the python module containing the class. A new class
    instance is then created with the given name.
    :param component: component name to load (in the form of module_name.class_name)
    :param name: optional name to give to the process
    :return: the component instance (the process)
    """
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


class TestComponent(Component):
    _in = IN()
    _out = OUT()

    def __init__(self, name=None):
        super().__init__(name)
