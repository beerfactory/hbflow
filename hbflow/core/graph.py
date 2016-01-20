from uuid import uuid4
from datetime import datetime
from hbflow.utils import InstanceCounterMeta
from .component import new_component_instance, Connection, Component
import logging

class GraphException(Exception):
    pass


class Graph(object, metaclass=InstanceCounterMeta):
    # states = ['new', 'resolved', 'unresolved', 'running', 'idle', 'stopping', 'stopped', 'shutdown']

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


