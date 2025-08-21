'''BEAM external term decoding
'''
from struct import unpack
from .exceptions import UnsupportedBeamExt

class BeamValueExt(object):
    def __init__(self, value):
        self.__value = value

    @property
    def value(self):
        return self.__value
    
    def __repr__(self):
        return '%s(%s)' % (
            self.__class__.__name__,
            str(self.__value)
        )

class BeamAtomCacheRef(BeamValueExt):

    def __init__(self, ref_index):
        super().__init__(ref_index)

    @staticmethod
    def parse(content):
        return BeamAtomCacheRef(unpack('>B', content.read(1))[0])

    def __str__(self):
        return 'BeamAtomCacheRef()'

class BeamSmallIntegerExt(BeamValueExt):

    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def parse(content):
        return BeamSmallIntegerExt(unpack('>B', content.read(1))[0])

    def __str__(self):
        return '0x%x' % self.value

class BeamIntegerExt(BeamValueExt):

    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def parse(content):
        return BeamIntegerExt(unpack('>I', content.read(4))[0])

    def __str__(self):
        return '0x%x' % self.value

class BeamFloatExt(BeamValueExt):

    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def parse(content):
        return BeamFloatExt(content.read(31))

    def __str__(self):
        return '%s' % self.value

class BeamSmallTupleExt(object):

    def __init__(self, members):
        self.__members = members

    @property
    def members(self):
        return self.__members

    def __len__(self):
        return len(self.__members)

    @staticmethod
    def parse(content):
        tuple_value = []
        arity = unpack('>B', content.read(1))[0]
        for i in range(arity):
            tuple_value.append(BeamExtTerm.parse(content, marker_required=False))
        return BeamSmallTupleExt(tuple_value)

    def __repr__(self):
        return '(%s)' % ', '.join(map(str, self.__members))

    def __str__(self):
        return '(%s)' % ', '.join(map(str, self.__members))

class BeamLargeTupleExt(BeamSmallTupleExt):
    def __init__(self, members):
        super().__init__(members)

    @staticmethod
    def parse(content):
        tuple_value = []
        arity = unpack('>I', content.read(4))[0]
        for i in range(arity):
            tuple_value.append(BeamExtTerm.parse(content, marker_required=False))
        return BeamLargeTupleExt(tuple_value)

    def __repr__(self):
        return '(%s)' % ', '.join(map(str, self.members))

    def __str__(self):
        return '(%s)' % ', '.join(map(str, self.members))

class BeamMapExt(object):
    def __init__(self):
        self.__map = {}

    def set(self, key, value):
        '''Set key=>value
        '''
        self.__map[key] = value

    @staticmethod
    def parse(content):
        map_obj = BeamMapExt()

        arity = unpack('>I', content.read(4))[0]
        for i in range(arity):
            key = BeamExtTerm.parse(content, marker_required=False)
            value = BeamExtTerm.parse(content, marker_required=False)
            map_obj.set(key, value)

        return map_obj

    def __repr__(self):
        key_values = []
        for key in self.__map:
            key_values.append("%s => %s" % (
                key, self.__map[key]
            ))
        return "{" + ", ".join(key_values) + "}"
 

class BeamListExt(object):

    def __init__(self):
        self.__items = []

    def append(self, item):
        self.__items.append(item)

    def __len__(self):
        return len(self.__items)

    def __getitem__(self, index):
        if index < len(self.__items):
            return self.__items[index]
        raise IndexError

    @staticmethod
    def parse(content):
        '''Parse list content
        '''
        list_obj = BeamListExt()

        list_size = unpack('>I', content.read(4))[0]
        for i in range(list_size):
            list_obj.append(BeamExtTerm.parse(content, marker_required=False))
        tail = BeamExtTerm.parse(content, marker_required=False)

        return list_obj

    def __str__(self):
        members = ', '.join([str(i) for i in self.__items])
        return "[%s]" % members

class BeamNilExt(object):
    def __init__(self):
        pass

    @staticmethod
    def parse(content):
        return BeamNilExt()

    def __str__(self):
        return 'NIL'

class BeamStringExt(BeamValueExt):
    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def parse(content):
        length = unpack('>H', content.read(2))[0]
        return BeamStringExt(content.read(length))

    def __repr__(self):
        return '"%s"' % self.value.decode('latin1').replace('\n', "\\n").replace('\r', "\\r")

class BeamBinaryExt(BeamValueExt):
    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def parse(content):
        length = unpack('>I', content.read(4))[0]
        return BeamBinaryExt(content.read(length))

    def __repr__(self):
        return '%s' % self.value

class BeamSmallBigExt(object):
    def __init__(self, sign, value):
        self.__sign = sign
        self.__value = value

    @property
    def value(self):
        value = 0
        for i,v in enumerate(self.__value):
            value += v*(256**i)
        if self.__sign==1:
            value = -value
        return value

    def __repr__(self):
        return '%s(%d)' % (
            self.__class__.__name__,
            self.value
        )

    @staticmethod
    def parse(content):
        n = unpack('>B', content.read(1))[0]
        sign = unpack('>B', content.read(1))[0]
        value = content.read(n)
        return BeamSmallBigExt(sign, value)

class BeamExportExt(object):
    def __init__(self, module, function, arity):
        self.__module = module
        self.__function = function
        self.__arity = arity

    @staticmethod
    def parse(content):
        module = BeamExtTerm.parse(content, marker_required=False)
        function = BeamExtTerm.parse(content, marker_required=False)
        arity = BeamExtTerm.parse(content, marker_required=False)
        return BeamExportExt(module.value, function.value, arity.value)

    def __repr__(self):
        return f'fun {self.__module.decode("utf-8")}:{self.__function.decode("utf-8")}/{self.__arity}'

class BeamLargeBigExt(BeamSmallBigExt):
    def __init__(self, sign, value):
        super().__init__(sign, value)

    @staticmethod
    def parse(content):
        n = unpack('>B', content.read(4))[0]
        sign = unpack('>B', content.read(1))[0]
        value = content.read(n)
        return BeamLargeBigExt(sign, value)        

class BeamNewFloatExt(BeamValueExt):
    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def parse(content):
        return BeamNewFloatExt(content.read(8))

class BeamAtomUtf8Ext(BeamValueExt):
    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def parse(content):
        length = unpack('>H', content.read(2))[0]
        return BeamAtomUtf8Ext(content.read(length))

    def __str__(self):
        return str(self.value.decode('utf-8'))
    
class BeamSmallAtomUtf8Ext(BeamAtomUtf8Ext):
    def __init__(self, value):
        super().__init__(value)

    def __str__(self):
        return str(self.value.decode('utf-8'))

    @staticmethod
    def parse(content):
        length = unpack('>B', content.read(1))[0]
        return BeamSmallAtomUtf8Ext(content.read(length))

class BeamAtomExt(BeamAtomUtf8Ext):
    def __init__(self, value):
        super().__init__(value)

class BeamSmallAtomExt(BeamAtomUtf8Ext):
    def __init__(self, value):
        super().__init__(value)

class BeamExtTerm(object):

    PARSERS = {
        70: BeamNewFloatExt,
        82: BeamAtomCacheRef,
        97: BeamSmallIntegerExt,
        98: BeamIntegerExt,
        100: BeamAtomExt,
        104: BeamSmallTupleExt,
        105: BeamLargeTupleExt,
        106: BeamNilExt,
        107: BeamStringExt,
        108: BeamListExt,
        109: BeamBinaryExt,
        110: BeamSmallBigExt,
        113: BeamExportExt,
        115: BeamSmallAtomExt,
        116: BeamMapExt,
        118: BeamAtomUtf8Ext,
        119: BeamSmallAtomUtf8Ext,
    }

    @staticmethod
    def parse(content, marker_required=True):
        '''Parse external term
        '''
        # Read marker and tag
        if marker_required:
            marker, tag = unpack('>BB', content.read(2))
            assert marker == 131
        else:
            tag = unpack('>B', content.read(1))[0]

        # Parse depending on tag
        if tag in BeamExtTerm.PARSERS:
            parser = BeamExtTerm.PARSERS[tag]
            return parser.parse(content)
        else:
            raise UnsupportedBeamExt(tag)
