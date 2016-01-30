# Copyright (c) 2016 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import unittest
import logging
from hbflow.utils import IdentifiableObject

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)
log = logging.getLogger(__name__)


class IdentifiableObjectTest(unittest.TestCase):
    def test_identifiable_1(self):
        class A(IdentifiableObject):
            def __init__(self):
                super().__init__()

        a = A()
        self.assertEquals(a._seq_id, 1)
        self.assertEquals(a._instance_name, 'A_1')

    def test_identifiable_2(self):
        class B(IdentifiableObject):
            def __init__(self):
                super().__init__()
        b1 = B()
        b2 = B()
        self.assertEquals(b1._seq_id, 1)
        self.assertEquals(b1._instance_name, 'B_1')
        self.assertEquals(b2._seq_id, 2)
        self.assertEquals(b2._instance_name, 'B_2')
