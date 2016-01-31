from uuid import uuid4
from datetime import datetime
from hbflow.utils import IdentifiableObject
from .component import get_component_class, OUT, IN, Connection, Component
from collections import namedtuple
import logging


class GraphException(Exception):
    pass


ProcessDesc = namedtuple('ProcessDesc', ['process_name', 'class_name', 'group'])
ConnectionDesc = namedtuple('ConnectionDesc',
                            ['connection_name',
                             'source_process_name',
                             'source_port_name',
                             'target_process_name',
                             'target_port_name', 'capacity'])


class Graph(IdentifiableObject):

    def __init__(self, name=None, description=None, author=None, date=datetime.now()):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        if name:
            self.name = name
        self.description = description
        self.author = author
        self.date = date
        self.id = uuid4()
        self.processes_desc = []
        self.connections_desc = []

    def add_process(self, process_name, component, group=None):
        self.processes_desc.append(ProcessDesc(process_name, component, group))

    def add_connection(self, connection_name, source_process_name, source_port_name, target_process_name, target_port_name, capacity):
        self.connections_desc.append(ConnectionDesc(connection_name, source_process_name, source_port_name, target_process_name, target_port_name, capacity))
