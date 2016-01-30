import logging
import asyncio
from transitions import Machine
from .component import new_component_instance, ComponentException
from .graph import Graph, Connection, GraphException


class EngineException(Exception):
    pass


class GraphEngine:
    states = ['new', 'resolved', 'unresolved', 'running', 'idle', 'stopping', 'stopped', 'shutdown']
    transitions = [
        {'trigger': 'resolve', 'source': 'new', 'dest': 'resolved'},
        {'trigger': 'resolve', 'source': 'unresolved', 'dest': 'resolved'},
        {'trigger': 'unresolve', 'source': 'new', 'dest': 'unresolved'},
        {'trigger': 'run', 'source': ['resolved', 'idle'], 'dest': 'running'},
        {'trigger': 'idle', 'source': 'running', 'dest': 'idle'},
        {'trigger': 'stop', 'source': ['running', 'idle'], 'dest': 'stopping'},
        {'trigger': 'stop', 'source': 'stopping', 'dest': 'stopped'},
        {'trigger': 'shutdown', 'source': 'stopped', 'dest': 'shutdown'},
    ]

    def __init__(self, graph=None, loop=None):
        self.logger = logging.getLogger(__name__)
        self.state = Machine(states=GraphEngine.states, transitions=GraphEngine.transitions, initial='new')
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()
        self.processes = dict()
        self.connections = dict()
        self._graph = None
        if graph:
            self.bind(graph)

    def bind(self, g):
        if not (self.state.is_new() or self.state.is_shutdown()):
            raise EngineException("Engine is already bounded to a graph instance")
        self._graph = g
        self._init_graph()

    def init_from_dictionary(self, dict_spec: dict):
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
            graph.add_connection(cnx_name, source_component, source_port, target_component, target_port, cnx_capacity)

        self.bind(graph)

    def _get_process_or_raise(self, process_name):
        """
        Get a process by its name. Raises a GraphException if no process is found
        :param self:
        :param process_name:
        :return:
        """
        try:
            src = self.processes[process_name]
            return src
        except KeyError:
            raise GraphException("Unkown process '%s'" % process_name)

    def _init_processes(self):
        for k in self._graph.processes_desc:
            proc_desc = self._graph.processes_desc[k]
            try:
                self.processes[proc_desc.process_name] = new_component_instance(proc_desc.class_name, proc_desc.process_name)
                self.logger.debug("Process '%s' created" % proc_desc.process_name)
            except ComponentException as ce:
                raise GraphException("Process '%s' instanciation failed" % proc_desc.process_name) from ce

    def _init_connections(self):
        for k in self._graph.connections_desc:
            cnx_desc = self._graph.connections_desc[k]

            # find source : source process output port
            source_port = None
            try:
                source_process = self._get_process_or_raise(cnx_desc.source_process_name)
                source_port = source_process.output_port(cnx_desc.source_port_name)
            except GraphException as ge:
                raise GraphException("Can't create connection '%s'" % cnx_desc.connection_name) from ge
            if not source_port:
                raise GraphException("Can't create connection '%s' : Source process '%s' has no output port named '%s'" %
                                     (cnx_desc.connection_name, source_process.name, cnx_desc.source_port_name))

            # find target : target process input port
            target_port = None
            try:
                target_process = self._get_process_or_raise(cnx_desc.target_process_name)
                target_port = target_process.input_port(cnx_desc.target_port_name)
            except GraphException as ge:
                raise GraphException("Can't create connection '%s'" % cnx_desc.connection_name) from ge
            if not target_port:
                raise GraphException("Can't create connection '%s' : Target process '%s' has no input port named '%s'" %
                                     (cnx_desc.connection_name, target_process.name, cnx_desc.target_port_name))

            cnx = Connection(cnx_desc.connection_name)
            if cnx.name in self.connections:
                raise GraphException("Duplicate connection name '%s'" % cnx.name)
            cnx.link(source_port, target_port)
            self.connections[cnx.name] = cnx
            self.logger.debug("Connection '%s' created" % cnx_desc.connection_name)

    def _init_graph(self):
        self.processes = dict()
        self.connections = dict()
        try:
            self._init_processes()
            self._init_processes()
            self.state.resolve()
        except GraphException as ge:
            self.state.unresolve()
            raise ge
