import logging
import asyncio
from transitions import Machine
from .component import new_component_instance, ComponentException, Component, OUT, IN
from .graph import Graph, Connection, GraphException
from .packet import CommandPacket
from .commands import *


class EngineException(Exception):
    pass


class ProcessManager(Component):

    command_out = OUT()
    status_in = IN()

    def __init__(self, name=None):
        super().__init__(name)

    async def send_command(self, command):
        await  self.command_out.send_packet(CommandPacket(command))


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
        self._process_manager = None
        if graph:
            self.bind(graph)

    async def bind(self, g):
        """
        Bind the engine to a graph description and instantiates processes
        :param g:
        :return:
        """
        if not (self.state.is_new() or self.state.is_shutdown()):
            raise EngineException("Engine is already bounded to a graph instance")
        self._graph = g
        await self._init_graph()

    async def init_from_dictionary(self, dict_spec: dict):
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

        await self.bind(graph)

    def _get_process(self, process_name, silent=True):
        """
        Get a process by its name. Raises a GraphException if no process is found
        :param self:
        :param process_name:
        :return:
        """
        return [p for p in self.processes.values() if p.name == process_name]

    async def _init_processes(self):
        for proc_desc in self._graph.processes_desc:
            try:
                process = new_component_instance(proc_desc.class_name, proc_desc.process_name)
                self.processes[process.id] = process
                self.logger.debug("Process '%s' created (Id=%s)" % (process.name, process.id))
            except ComponentException as ce:
                raise GraphException("Process '%s' instanciation failed" % process.name) from ce

    async def _init_connections(self):
        for cnx_desc in self._graph.connections_desc:

            # find source : source process output port
            source_port = None
            try:
                process_list = self._get_process(cnx_desc.source_process_name)
                if len(process_list) > 1:
                    raise GraphException("Can't create connection '%s': ambiguous process name '%s'" % (cnx_desc.connection_name, cnx_desc.source_process_name))
                else:
                    source_process = process_list[0]
                source_port = source_process.output_port(cnx_desc.source_port_name)
            except GraphException as ge:
                raise GraphException("Can't create connection '%s'" % cnx_desc.connection_name) from ge
            if not source_port:
                raise GraphException("Can't create connection '%s' : Source process '%s' has no output port named '%s'" %
                                     (cnx_desc.connection_name, source_process.name, cnx_desc.source_port_name))

            # find target : target process input port
            target_port = None
            try:
                process_list = self._get_process(cnx_desc.target_process_name)
                if len(process_list) > 1:
                    raise GraphException("Can't create connection '%s': ambiguous process name '%s'" % (cnx_desc.connection_name, cnx_desc.target_process_name))
                else:
                    target_process = process_list[0]
                target_port = target_process.input_port(cnx_desc.target_port_name)
            except GraphException as ge:
                raise GraphException("Can't create connection '%s'" % cnx_desc.connection_name) from ge
            if not target_port:
                raise GraphException("Can't create connection '%s' : Target process '%s' has no input port named '%s'" %
                                     (cnx_desc.connection_name, target_process.name, cnx_desc.target_port_name))

            cnx = Connection(cnx_desc.connection_name)
            cnx.link(source_port, target_port)
            self.connections[cnx.id] = cnx
            self.logger.debug("Connection '%s' created" % cnx_desc.connection_name)

    async def _init_process_manager(self):
        self._process_manager = ProcessManager()
        for process in self.processes.values():
            cnx = Connection()
            cnx.link(self._process_manager.command_out, process._command_in)

    async def _init_graph(self):
        self.processes = dict()
        self.connections = dict()
        try:
            await self._init_processes()
            await self._init_connections()
            await self._init_process_manager()
            self.state.resolve()
        except GraphException as ge:
            self.state.unresolve()
            raise ge

    async def start(self):
        await self._process_manager.send_command(START)
