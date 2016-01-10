# Copyright (c) 2016 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import logging
import unittest
import yaml
import asyncio

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)
log = logging.getLogger(__name__)


def read_yaml(file):
    dict = None
    try:
        with open(file, 'r') as stream:
            dict = yaml.load(stream)
    except yaml.YAMLError as exc:
        log.error("Invalid config_file %s: %s" % (file, exc))
    return dict


class GraphTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_create_from_dictionary(self):
        yaml_config = """
graph:
  name : Graph
  description: some description
  author: Nico
  revision : 1.0
  date : 2016-01-10
                """
        dict = yaml.load(yaml_config)
        print(dict)