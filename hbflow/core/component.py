import logging
import asyncio
from uuid import uuid4
from transitions import Machine
from hbflow.utils import IdentifiableObject
from hbflow.core.packet import Packet, CommandPacket
from hbflow.core.commands import *
import importlib


class ComponentException(Exception):
    pass


class Port(IdentifiableObject):
    def __init__(self, name, component, description=None, display_name=None, loop=None):
        super().__init__()
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()
        if name:
            self.name = name
        else:
            self.name = self._instance_name
        self.component = component
        self.description = description
        self.display_name = display_name
        self.connections = []
        self.connected_event = asyncio.Event()

    def add_connection(self, connection):
        self.connections.append(connection)
        if not self.connected_event.is_set():
            self.connected_event.set()

    def remove_connection(self, connection):
        self.connections.remove(connection)
        if not self.connections:
            self.connected_event.clear()


class InputPort(Port):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def read_packet(self):
        await self.connected_event.wait()
        futures = []
        for cnx in self.connections:
            futures.append(cnx.get_packet())
        if futures:
            done, pending = await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED, loop=self._loop)
            packet = done.pop().result()
            return self, packet
        else:
            return self, None


class OutputPort(Port):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def send_packet(self, packet):
        for cnx in self.connections:
            await cnx.put_packet(packet)


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

    def __init__(self, name=None, capacity=1):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.id = uuid4()
        self.state = Machine(states=Connection.states, initial='new')
        if name:
            self.name = name
        else:
            self.name = self._instance_name
        self.capacity = capacity
        self.packet_queue = asyncio.Queue(self.capacity)
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
        self.state.to_linked()

    def unlink(self):
        self.logger.debug("Linked removed: %s:%s -> %s:%s" % (self.source.component.name, self.source.name, self.target.component.name, self.target.name))
        self.source = None
        self.target = None
        # Todo: remove connection from source and target
        self.state.to_unlinked()

    async def put_packet(self, packet):
        await self.packet_queue.put(packet)

    async def get_packet(self):
        packet = await self.packet_queue.get()
        return packet

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

    def __new__(cls, name=None, loop=None):
        instance = super().__new__(cls)
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, IN):
                setattr(instance, attr_name, InputPort(attr_name, instance, attr.description, attr.display_name, loop))
            elif isinstance(attr, OUT):
                setattr(instance, attr_name, OutputPort(attr_name, instance, attr.description, attr.display_name, loop))
        return instance

    def __init__(self, name=None, loop=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()
        self.machine = Machine(model=self, states=Component.states, transitions=Component.transitions, initial='new')
        self.id = uuid4()
        if name:
            self.name = name
        else:
            self.name = self._instance_name
        asyncio.ensure_future(self._packet_loop(), loop=self._loop)

    def input_port(self, port_name):
        return getattr(self, port_name, None)

    def output_port(self, port_name):
        return getattr(self, port_name, None)

    async def _packet_loop(self):
        while True:
            self._futures = []
            self._futures.append(self._command_in.read_packet())
            if self._futures:
                done, pending = await asyncio.wait(self._futures, return_when=asyncio.FIRST_COMPLETED, loop=self._loop)
            if done:
                task = done.pop()
                input_port, packet = task.result()
                if packet:
                    if isinstance(packet, CommandPacket):
                        await self._handle_command(packet)
                    else:
                        await self.on_packet(input_port, packet)
                else:
                    self.logger.warning("Empty packet received")

    async def _handle_command(self, packet: CommandPacket):
        if not packet.command:
            self.logger.warning("Invalid command packet received")
            return
        func_name = '_handle_command_' + packet.command
        try:
            func = getattr(self, func_name)
            func(packet)
        except AttributeError:
            self.logger.warning("Command '%s' ignored (no handler)" % packet.command)

    async def on_packet(self, from_port: InputPort, packet: Packet):
        pass


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
