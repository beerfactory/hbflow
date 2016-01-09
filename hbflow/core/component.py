
def IN(name, description=None, display_name=None, array_size=1):
    def wrapper(cls):
        if not hasattr(cls, 'in_port_defs'):
            raise TypeError("class %s incompatible with IN decorator" % cls.__name__)
        if name in cls.in_port_defs:
            raise ValueError("IN port '%s' already exists" % name)

        cls.in_port_defs[name] = (name, description, display_name, array_size)
        return cls
    return wrapper

def OUT(cls, name, *args, **kwargs):
    if not hasattr(cls, 'out_port_defs'):
        raise TypeError("class %s incompatible with OUT decorator" % cls.__name__)
    if name in cls.out_port_defs:
        raise ValueError("OUT port '%s' already exists" % name)

    description = kwargs.get('description', None)
    display_name = kwargs.get('display_name', None)
    array_size = kwargs.get('array_size', 1)
    cls.out_port_defs[name] = (name, description, display_name, array_size)\


@IN(name="debug")
class Component:
    in_port_defs = dict()
    out_port_defs = dict()

    _debug = InPort()

    def __init__(self):
        pass


class Port:
    def __init__(self, description='', display_name='', array_size=1):
        self.description = description
        self.display_name = display_name
        self.array_size = array_size


class InPort(Port):
    pass


class OutPort(Port):
    pass
