import yaml
import logging
from hbflow.core.component import Graph

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
    g = Graph.init_from_dictionary(config)
    print(g.processes)