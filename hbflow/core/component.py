from collections import namedtuple
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


class Graph(object, metaclass=InstanceCounterMeta):
    states = ['new', 'resolved', 'unresolved', 'running', 'idle', 'stopping', 'stopped', 'shutdown']

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._seq_id = next(cls._ids)
        instance.name = cls.__name__ + "_" + str(instance._seq_id)
        return instance

    def __init__(self, name=None, description=None, author=None, date=datetime.now()):
        self.logger = logging.getLogger(__name__)
        if name:
            self.name = name
        self.description = description
        self.author = author
        self.date = date
        self.id = uuid4()
        self.processes = dict()
        self.connections = dict()

    def add_process(self, name, component_name, group=None):
        if name in self.processes:
            raise GraphException("Duplicate process name '%s'" % name)
        self.processes[name] = new_component_instance(component_name, name)
        # To be removed
        if group:
            self.logger.warning("Process not implemented yet. Adding '%s' process to root" % name)

    def _get_process_or_raise(self, process_name):
        try:
            src = self.processes[process_name]
            return src
        except KeyError:
            raise GraphException("Unkown process '%s'" % process_name)

    def add_connection(self, source_process, source_port_name, target_process, target_port_name, capacity, connection_name=None):
        # find source : source process output port
        if isinstance(source_process, str):
            try:
                src = self._get_process_or_raise(source_process)
            except GraphException as ge:
                raise GraphException("Can't create connection '%s'" % connection_name) from ge
        elif isinstance(source_process, Component):
            src = source_process
        else:
            raise ValueError("Incompatible type for source process")
        src_port = src.output_port(source_port_name)
        if not src_port:
            raise GraphException("Can't create connection '%s' : Source process '%s' has no output port named '%s'" %
                                 (connection_name, src.name, source_port_name))

        # find target : target process input port
        if isinstance(target_process, str):
            try:
                target = self._get_process_or_raise(target_process)
            except GraphException as ge:
                raise GraphException("Can't create connection '%s'" % connection_name) from ge
        elif isinstance(target_process, Component):
            target = source_process
        else:
            raise ValueError("Incompatible type for target process")
        target_port = target.input_port(target_port_name)
        if not target_port:
            raise GraphException("Can't create connection '%s' : Target process '%s' has no input port named '%s'" %
                                 (connection_name, src.name, source_port_name))

        cnx = Connection(connection_name)
        if cnx.name in self.connections:
            raise GraphException("Duplicate connection name '%s'" % cnx.name)
        cnx.link(src_port, target_port)
        self.connections[cnx.name] = cnx

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
            component_name = processes[process].get('component', None)
            if not component_name:
                raise GraphException("No component class given for process '%s'", process)
            graph.add_process(process, component_name)

        connections = graph_config.get('connections')
        for cnx in connections:
            try:
                source_component = cnx['source']['process']
                source_port = cnx['source']['port']
                target_component = cnx['target']['process']
                target_port = cnx['target']['port']
                cnx_capacity = cnx.get('capacity', 1) # TODO: don't hard-code, use default
                cnx_name = cnx.get('name', None)
            except KeyError as ke:
                raise GraphException("Invalid parameters for connection '%s' definition" % cnx_name) from ke
            graph.add_connection(source_component, source_port, target_component, target_port, cnx_capacity, cnx_name)
        return graph


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

# def IN(name, description=None, display_name=None, array_size=1):
#     def wrapper(cls):
#         if cls:
#             print(cls)
#             if not hasattr(cls, '_in_port_defs'):
#                 raise TypeError("class '%s' incompatible with IN decorator" % cls.__name__)
#             if name in cls._in_port_defs:
#                 raise ValueError("IN port '%s' already exists" % name)
#
#             cls._in_port_defs[name] = (description, display_name, array_size)
#             return cls
#     return wrapper


# def OUT(name, *args, **kwargs):
#     def wrapper(cls):
#         if not hasattr(cls, '_out_port_defs'):
#             raise TypeError("class '%s' incompatible with OUT decorator" % cls.__name__)
#         if name in cls._out_port_defs:
#             raise ValueError("OUT port '%s' already exists" % name)
#
#         description = kwargs.get('description', None)
#         display_name = kwargs.get('display_name', None)
#         array_size = kwargs.get('array_size', 1)
#         cls._out_port_defs[name] = (description, display_name, array_size)
#     return wrapper



class Component(object, metaclass=InstanceCounterMeta):
    states = ['new', 'starting', 'waiting', 'running', 'idle', 'stopping', 'stopped', 'shutdown']
    transitions = [
        {'trigger': 'initialize', 'source': 'new', 'dest': 'ready'},
        {'trigger': 'start', 'source': 'new', 'dest': 'starting'},
        {'trigger': 'start', 'source': 'starting', 'dest': 'idle'},
        {'trigger': 'run', 'source': ['idle', 'waiting'], 'dest': 'running'},
        {'trigger': 'wait', 'source': 'running', 'dest': 'waiting'},
        {'trigger': 'idle', 'source': 'running', 'dest': 'idle'},
        {'trigger': 'stop', 'source': ['running', 'waiting'], 'dest': 'stopping'},
        {'trigger': 'stop', 'source': 'stopping', 'dest': 'stopped'},
        {'trigger': 'shutdown', 'source': 'stopped', 'dest': 'sshutdown'},
    ]

    _debug_in = IN()
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
