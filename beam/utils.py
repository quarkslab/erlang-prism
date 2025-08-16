'''Erlang BEAM utility functions.
'''

from .exceptions import UnsupportedBeamCompactTerm
from .types import BeamAtom, BeamInteger, BeamChar, BeamLabel, BeamLiteral, \
    BeamNIL, BeamXReg, BeamYReg, BeamExtList, BeamExtAllocList, BeamFpReg, BeamTypedReg

class BeamCompactTerm(object):

    TYPE_LIT = 0
    TYPE_INT = 1
    TYPE_ATOM = 2
    TYPE_XREG = 3
    TYPE_YREG = 4
    TYPE_LBL = 5
    TYPE_CHAR = 6

    # OTP20, float is considered as a literal
    TYPE_EXT_LIST = 0x17
    TYPE_EXT_FPREG = 0x27
    TYPE_EXT_ALST = 0x37
    TYPE_EXT_LIT = 0x47
    TYPE_EXT_TYPED_REG = 0x57

    DECODERS = {
        TYPE_LIT: BeamLiteral,
        TYPE_INT: BeamInteger,
        TYPE_ATOM: BeamAtom,
        TYPE_XREG: BeamXReg,
        TYPE_YREG: BeamYReg,
        TYPE_LBL: BeamLabel,
        TYPE_CHAR: BeamChar,
    }

    @staticmethod
    def decode_value(source, value, value_type):
        '''Decode value based on type
        '''
        if value_type in BeamCompactTerm.DECODERS:
            return BeamCompactTerm.DECODERS[value_type](value)
        else:
            raise UnsupportedBeamCompactTerm

    @staticmethod
    def decode_ext(source, value_type):
        '''Decode extended value
        '''
        #print('compact term: 0x%02x' % value_type)

        # Typed register
        if value_type == BeamCompactTerm.TYPE_EXT_TYPED_REG:
            reg = BeamCompactTerm.read_term(source)
            reg_type = BeamCompactTerm.read_term(source)
            return BeamTypedReg(reg, reg_type)
        # Allocation list
        elif value_type == BeamCompactTerm.TYPE_EXT_LIT:
            # Read tag and value
            literal = BeamCompactTerm.read_term(source)
            if isinstance(literal, BeamLiteral):
                return literal
            else:
                raise UnsupportedBeamCompactTerm
        elif value_type == BeamCompactTerm.TYPE_EXT_LIST:
            # Read smallint
            list_obj = BeamExtList()
            literal = BeamCompactTerm.read_term(source)
            for i in range(int(literal.index)):
                #key = BeamCompactTerm.read_term(source)
                value = BeamCompactTerm.read_term(source)
                list_obj.add(value)
            return list_obj
        elif value_type == BeamCompactTerm.TYPE_EXT_ALST:
            # Read smallint
            list_obj = BeamExtAllocList()
            literal = BeamCompactTerm.read_term(source)
            for i in range(int(literal.index)):
                key = BeamCompactTerm.read_term(source)
                value = BeamCompactTerm.read_term(source)
                list_obj.add(key, value)
            return list_obj
        elif value_type == BeamCompactTerm.TYPE_EXT_FPREG:
            # Read tag and value
            literal = BeamCompactTerm.read_term(source)
            if isinstance(literal, BeamLiteral):
                return BeamFpReg(literal.index)
            else:
                raise UnsupportedBeamCompactTerm
        raise UnsupportedBeamCompactTerm
 
    @staticmethod
    def read_term(source):
        '''Read a tag.
        '''
        # Read 1 byte
        b0 = ord(source.read(1))
        # Deduce type
        if b0 & 0x07 == 0x07:
            # Extended type, type is coded in a whole byte
            value_type = b0

            return BeamCompactTerm.decode_ext(source, value_type)
        else:
            # Basic type, let's decode it
            value_type = b0 & 0x07
            if (b0 & (1 << 3)):
                if (b0 & (1 << 4)):
                    if (b0 >> 5) == 7:
                        value_len = BeamCompactTerm.read_term(source).index + 9
                        value = source.read(value_len)
                    else:
                        value_len = (b0 >> 5) + 2
                        value = source.read(value_len)
                else:
                    value = ((b0 & 0xE0)<<3) | ord(source.read(1))
            else:
                value = b0 >> 4

            return BeamCompactTerm.decode_value(source, value, value_type)
