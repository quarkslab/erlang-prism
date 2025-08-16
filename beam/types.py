'''BEAM types
'''
from struct import unpack
from .exceptions import UnsupportedBeamCompactTerm

def bytes_to_int(b):
    value = 0
    for i in range(len(b)):
        value = (value<<8)
        value |= b[i]
    return value

class BeamNIL(object):
    pass

class BeamInteger(object):
    '''Represents a BEAM integer value.
    '''
    def __init__(self, value):
        super().__init__()
        if isinstance(value, int):
            self.__value = value
        elif isinstance(value, bytes):
            v = 0
            for i in range(len(value)-1, -1, -1):
                v += (256**i)*(value[len(value)-1-i])
            self.__value = v
        else:
            raise UnsupportedBeamCompactTerm

    @property
    def value(self):
        return self.__value

    def __repr__(self):
        return 'BeamInteger(%d)' % self.value
    
class BeamLiteral(object):
    '''Represents a BEAM literal
    '''
    def __init__(self, index):
        super().__init__()
        if isinstance(index, int):
            self.__index = index
        elif isinstance(index, bytes):
            self.__index = bytes_to_int(index)
        else:
            raise UnsupportedBeamCompactTerm

    @property
    def index(self):
        return self.__index

    def __repr__(self):
        return 'BeamLiteral(%d)' % self.index

class BeamLabel(BeamLiteral):
    '''Represents a BEAM label
    '''
    def __init__(self, index):
        super().__init__(index)

    def __repr__(self):
        return 'BeamLabel(%d)' % self.index

class BeamAtom(object):
    '''Represents a BEAM Atom
    '''
    def __init__(self, index):
        super().__init__()
        if isinstance(index, int):
            self.__index = index
        elif isinstance(index, bytes):
            self.__index = bytes_to_int(index)
        else:
            raise UnsupportedBeamCompactTerm

    @property
    def index(self):
        if self.__index == 0:
            return BeamNIL()
        else:
            return self.__index

    def is_nil(self):
        return self.__index == 0

    def __repr__(self):
        if self.is_nil():
            return 'BeamNIL()'
        else:
            return 'BeamAtom(%d)' % self.index

class BeamXReg(object):
    '''Represents an X register
    '''
    def __init__(self, index):
        super().__init__()
        self.__index = index

    @property
    def index(self):
        return self.__index

    def __repr__(self):
        return 'X%d' % self.index
    
class BeamYReg(BeamXReg):
    '''Represents an Y register
    '''
    def __init__(self, index):
        super().__init__(index)

    def __repr__(self):
        return 'Y%d' % self.index

class BeamChar(object):
    '''Represents a character (unicode)
    '''
    def __init__(self, value):
        super().__init__()
        self.__char_value = value

    @property
    def value(self):
        return chr(self.__char_value)

    def __repr__(self):
        return 'BeamChar(%s)' % self.__char_value
    
class BeamExtList(object):
    '''Represents a BEAM extended list
    '''
    def __init__(self):
        super().__init__()
        self.__items = []

    def __len__(self):
        return len(self.__items)

    def __getitem__(self, index):
        if index < len(self.__items):
            return self.__items[index]
        raise IndexError

    def add(self, item):
        self.__items.append(item)

    def __repr__(self):
        #pairs = ','.join(['(%s, %s)' % (str(k), str(v)) for k,v in self.__pairs])
        items = ','.join(['%s' % str(v) for v in self.__items])
        return 'BeamList(%s)' % items

class BeamExtAllocList(object):
    '''Represents a BEAM extended allocation list
    '''
    def __init__(self):
        super().__init__()
        self.__items = []

    def __len__(self):
        return len(self.__items)

    def __getitem__(self, index):
        if index < len(self.__items):
            return self.__items[index]
        raise IndexError

    def add(self, key, value):
        self.__items.append((key, value))

    def __repr__(self):
        #pairs = ','.join(['(%s, %s)' % (str(k), str(v)) for k,v in self.__pairs])
        items = ','.join(['%s' % str(v) for v in self.__items])
        return 'BeamAllocList(%s)' % items

class BeamFpReg(object):
    '''Represents an FR register
    '''
    def __init__(self, index):
        super().__init__()
        self.__index = index

    @property
    def index(self):
        return self.__index

    def __repr__(self):
        return 'FR%d' % self.index
    
class BeamTypedReg(object):
    '''Typed register
    '''

    def __init__(self, register, regtype):
        self.__reg = register
        self.__reg_type = regtype

    @property
    def register(self):
        return self.__reg

    @property
    def typeinfo(self):
        return self.__reg_type

    def __str__(self):
        return '{}<{}>'.format(self.__reg, self.__reg_type.index)
