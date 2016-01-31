import yaml
import logging
import asyncio
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

ge = GraphEngine()

async def test_coro():
    await ge.init_from_dictionary(config)
    await ge.start()
    await asyncio.sleep(1)


if __name__ == '__main__':
    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    log = logging.getLogger(__name__)
    config = read_yaml_config("basic.yaml")
    asyncio.get_event_loop().run_until_complete(test_coro())
    print(ge.processes)
