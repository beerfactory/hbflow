from uuid import uuid4
from datetime import datetime
from hbflow.utils import InstanceCounterMeta
from .component import get_component_class, OUT, IN, Connection, Component
from collections import namedtuple
import logging


class GraphException(Exception):
    pass


class GraphManager(Component):

    command_out = OUT()
    status_in = IN()

    def __init__(self, name=None):
        super().__init__(name)


ProcessDesc = namedtuple('ProcessDesc', ['process_name', 'class_name', 'group'])
ConnectionDesc = namedtuple('ConnectionDesc',
                            ['connection_name',
                             'source_process_name',
                             'source_port_name',
                             'target_process_name',
                             'target_port_name', 'capacity'])


class Graph(object, metaclass=InstanceCounterMeta):

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
        self.processes_desc = dict()
        self.connections_desc = dict()

    def add_process(self, process_name, component, group=None):
        if process_name in self.processes_desc:
            raise GraphException("Duplicate process name '%s'" % process_name)
        if group:
            self.logger.warning("Process not implemented yet. Adding '%s' process to root" % process_name)
        self.processes_desc[process_name] = ProcessDesc(process_name, component, group)

    def add_connection(self, connection_name, source_process_name, source_port_name, target_process_name, target_port_name, capacity):
        if connection_name in self.connections_desc:
            raise GraphException("Duplicate connection name '%s'" % connection_name)
        self.connections_desc[connection_name] = ConnectionDesc(connection_name, source_process_name, source_port_name, target_process_name, target_port_name, capacity)
