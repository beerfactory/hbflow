import yaml
import logging
from hbflow.core.graph import Graph
from hbflow.core.engine import GraphEngine

def read_yaml_config(config_file):
    config = None
    try:
        with open(config_file, 'r') as stream:
            config = yaml.load(stream)
    except yaml.YAMLError as exc:
        print("Invalid config_file %s: %s" % (config_file, exc))
    return config

if __name__ == "__main__":
    config = read_yaml_config("basic.yaml")
    ge = GraphEngine()
    ge.init_from_dictionary(config)
    ge.instantiate_graph()
    print(ge.processes)