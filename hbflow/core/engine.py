from .component import Graph, new_component_instance


class GraphEngine:
    def __init__(self, loop=None):
        self.graph = None

    @property
    def graph(self):
        return self.graph

    @graph.setter
    def graph(self, g):
        self.graph = g
