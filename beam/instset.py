'''BEAM instructions set
'''
import traceback
from struct import unpack
from .utils import BeamCompactTerm
from .types import BeamLabel, BeamExtList, BeamLiteral, BeamInteger

class BeamInstsRegistry(object):

    INSTS_CLAZZ = {}
    INSTS_ARITY = {}

    @staticmethod
    def register(clazz, opcode, arity):
        BeamInstsRegistry.INSTS_CLAZZ[opcode] = clazz
        BeamInstsRegistry.INSTS_ARITY[opcode] = arity

    @staticmethod
    def arity(opcode):
        if opcode in BeamInstsRegistry.INSTS_ARITY:
            return BeamInstsRegistry.INSTS_ARITY[opcode]
        raise IndexError

    @staticmethod
    def inst_class(opcode):
        if opcode in BeamInstsRegistry.INSTS_CLAZZ:
            return BeamInstsRegistry.INSTS_CLAZZ[opcode]
        raise BeamInst

class opcode(object):

    def __init__(self, opcode_num, arity):
        self.__opcode = opcode_num
        self.__arity = arity

    def __call__(self, clazz):
        clazz.opcode = self.__opcode
        clazz.arity = self.__arity
        BeamInstsRegistry.register(clazz, self.__opcode, self.__arity)
        return clazz

class jumpref_op(object):
    def __init__(self, *args):
        self.__targets = args

    def __call__(self, clazz):
        clazz.jumprefs = self.__targets
        return clazz

def exit_func(clazz):
    clazz.exit_func = True
    return clazz

def branch(clazz):
    clazz.is_branch = True
    return clazz

class BeamInst(object):
    '''Basic instruction class.
    '''

    jumprefs = []
    exit_func = False
    is_branch = False

    def __init__(self, mnemonic):
        self.__mnemonic = mnemonic
        self.__operands = []
        self.__annotations = []

    @property
    def mnemo(self):
        """Retrieve the instruction mnemonic
        """
        return self.__mnemonic

    @property
    def operands(self):
        """Retrieve instruction operands
        """
        return self.__operands

    @property
    def jump_targets(self):
        '''Check declared jumprefs operands
        '''
        targets = []
        for ref in self.jumprefs:
            if ref < len(self.__operands):
                operand = self.__operands[ref]
                if isinstance(operand, BeamLabel):
                    targets.append(operand.index)
                elif isinstance(operand, BeamExtList):
                    for v in operand:
                        if isinstance(v, BeamLabel):
                            targets.append(v.index)
        return targets

    def is_terminal(self):
        '''Check if this instruction is terminal.
        '''
        return self.exit_func

    def is_conditional(self):
        '''Check if this instruction performs a conditional jump
        '''
        return (self.is_branch  and (len(self.jump_targets) > 0))

    def add_operand(self, operand):
        """Add operand to the list of the operands.
        """
        self.__operands.append(operand)

    def add_annotation(self, annotation):
        """Add annotation to this instruction. Annotations are outputed before
        the instruction mnemonic and operand(s).
        """
        self.__annotations.append(annotation)

    def __repr__(self):
        """Retrieve the representation of this instruction, aka disassembled
        instruction.
        """
        operands = ' '.join([str(operand) for operand in self.__operands])
        return '%s %s' % (
            self.__mnemonic,
            operands
        )

    def format(self, module, format, operands):
        '''Format instruction based on module, format string and the provided
        operands.
        '''
        annotations = '\n'.join(self.__annotations)
        operands = list(operands)
        operands.insert(0, self.mnemo)
        return annotations + str('\t{:20}' + format).format(*operands)

    def get_value(self, operand):
        """Get operand value, whenever it's possible.
        """
        op = self.__operands[operand]
        if isinstance(op, BeamLiteral):
            return op.index
        elif isinstance(op, BeamInteger):
            return op.value

    def to_string(self, module):
        '''Resolve operands
        '''
        # Generate default format for the number of operands we have
        op_format = ', '.join(['{}' for i in range(len(self.operands))])
        return self.format(module, op_format, [
            module.get_value(x) for  x in self.operands
        ])

    @classmethod
    def parse_operands(cls, content):
        '''Parse operands based on arity
        '''
        inst = cls()
        for _ in range(cls.arity):
            inst.add_operand(BeamCompactTerm.read_term(content))
        return inst


@opcode(1, 1)
class BeamInstLabel(BeamInst):
    def __init__(self):
        super().__init__('label')
        self.__number = None

    def to_string(self, module):
        '''Label has only one operand, a literal indicating the label number.
        '''
        return 'label%d:' % int(self.operands[0].index)

@opcode(2, 3)
class BeamInstFuncInfo(BeamInst):
    def __init__(self):
        super().__init__('func_info')

    @property
    def module_atom(self):
        """Retrieve the module atom index.
        """
        return self.operands[0].index

    @property
    def name_atom(self):
        """Retrieve the module name atom index.
        """
        return self.operands[1].index

    @property
    def arity(self):
        """Retrieve the function arity (number of args).
        """
        return self.operands[2].index

    def to_string(self, module):
        '''Function info operands:
        - first operand is an atom referencing the module name
        - second operand is an atom referencing the function name
        - third operand is a literal representing the arity
        '''
        return self.format(module, '{}, {}, {:d}', [
            module.get_atom(self.operands[0].index),
            module.get_atom(self.operands[1].index),
            self.operands[2].index
        ])

@exit_func
@opcode(3, 0)
class BeamInstIntCodeEnd(BeamInst):
    def __init__(self):
        super().__init__('int_code_end')

@opcode(4, 2)
class BeamInstCall(BeamInst):
    def __init__(self):
        super().__init__('call')

    def to_string(self, module):
        return self.format(module, '{:d}, label{:d}', [
            self.operands[0].index,
            self.operands[1].index
        ])

@opcode(5, 3)
class BeamInstCallLast(BeamInst):
    def __init__(self):
        super().__init__('call_last')

    def to_string(self, module):
        '''Operands:
        - integer (literal)
        - label
        - integer (literal)
        '''
        return self.format(module, '{:d}, label{:d}, {:d}', [
            self.operands[0].index,
            self.operands[1].index,
            self.operands[2].index
        ])

@opcode(6, 2)
class BeamInstCallOnly(BeamInst):
    def __init__(self):
        super().__init__('call_only')

    def to_string(self, module):
        '''Operands:
        - integer (literal)
        - label
        - integer (literal)
        '''
        return self.format(module, '{:d}, label{:d}', [
            self.operands[0].index,
            self.operands[1].index
        ])

@opcode(7, 2)
class BeamInstCallExt(BeamInst):
    def __init__(self):
        super().__init__('call_ext')

    def to_string(self, module):
        '''Operands:
        - literal (int)
        - import func
        '''
        return self.format(module, '{:d}, {}', [
            self.operands[0].index,
            module.get_import_str(self.operands[1].index)
        ])

@opcode(8, 3)
class BeamInstCallExtLast(BeamInst):
    def __init__(self):
        super().__init__('call_ext_last')

    def to_string(self, module):
        return self.format(module, '0x{:X}, {}, 0x{:X}', [
            self.operands[0].index,
            module.get_import_str(self.operands[1].index),
            self.operands[2].index
        ])


@opcode(9, 2)
class BeamInstBif0(BeamInst):
    def __init__(self):
        super().__init__('bif0')

@opcode(10, 4)
class BeamInstBif1(BeamInst):
    def __init__(self):
        super().__init__('bif1')

    def to_string(self, module):
        '''Operands:
        - Label
        - Integer
        - Literal
        - reg
        - Integer
        - reg
        '''
        return self.format(module, 'label{:d}, {:d}, {}, {}', [
            self.operands[0].index,
            self.operands[1].index,
            module.get_value(self.operands[2]),
            module.get_value(self.operands[3])
        ])

@opcode(11, 5)
class BeamInstBif2(BeamInst):
    def __init__(self):
        super().__init__('bif2')

    def to_string(self, module):
        '''Operands:
        - Label
        - Integer
        - Literal
        - reg
        - Integer
        - reg
        '''
        return self.format(module, 'label{:d}, {:d}, {}, {}, {}', [
            self.operands[0].index,
            self.operands[1].index,
            module.get_value(self.operands[2]),
            module.get_value(self.operands[3]),
            module.get_value(self.operands[4])
        ])

@opcode(12, 2)
class BeamInstAllocate(BeamInst):
    def __init__(self):
        super().__init__('allocate')

    def to_string(self, module):
        return self.format(module, '{:d}, {:d}', [
            self.operands[0].index,
            self.operands[1].index
        ])

@opcode(13, 3)
class BeamInstAllocateHeap(BeamInst):
    def __init__(self):
        super().__init__('allocate_heap')

    def to_string(self, module):
        return self.format(module, '{}, {}, {}', [
            self.get_value(0),
            self.get_value(1),
            self.get_value(2),
        ])

@opcode(14, 2)
class BeamIntAllocateZero(BeamInst):
    def __init__(self):
        super().__init__('allocate_zero')

    def to_string(self, module):
        return self.format(module, '{:d}, {:d}', [
            self.operands[0].index,
            self.operands[1].index,
        ])

@opcode(15, 3)
class BeamInstAllocateHeapZero(BeamInst):
    def __init__(self):
        super().__init__('allocate_heap_zero')

    def to_string(self, module):
        return self.format(module, '{:d}, {:d}, {:d}', [
            self.operands[0].index,
            self.operands[1].index,
            self.operands[2].index,
        ])


@opcode(16, 2)
class BeamInstTestHeap(BeamInst):
    def __init__(self):
        super().__init__('test_heap')

    def to_string(self, module):
        '''Process each operand
        ''' 
        if isinstance(self.operands[0], BeamLiteral):
            first_operand = self.operands[0].index
        else:
            first_operand = module.get_value(self.operands[0])
        if isinstance(self.operands[1], BeamLiteral):
            second_operand = self.operands[1].index
        else:
            second_operand = module.get_value(self.operands[1])

        return self.format(module, '{}, {}', [
            first_operand,
            second_operand
        ])

@opcode(17, 1)
class BeamInstInit(BeamInst):
    def __init__(self):
        super().__init__('init')

@opcode(18, 1)
class BeamInstDeallocate(BeamInst):
    def __init__(self):
        super().__init__('deallocate')

    def to_string(self, module):
        return self.format(module, '{:d}', [
            self.operands[0].index
        ])

@exit_func
@opcode(19, 0)
class BeamInstReturn(BeamInst):
    def __init__(self):
        super().__init__('return')

@opcode(20, 0)
class BeamInstSend(BeamInst):
    def __init__(self):
        super().__init__('send')

@opcode(21, 0)
class BeamInstRemoveMessage(BeamInst):
    def __init__(self):
        super().__init__('remove_message')

@opcode(22, 0)
class BeamInstTimeout(BeamInst):
    def __init__(self):
        super().__init__('timeout')

@opcode(23, 2)
class BeamInstLoopRec(BeamInst):
    def __init__(self):
        super().__init__('loop_rec')

    def to_string(self, module):
        '''
        first operand: label
        second operand: reg
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
        ])

@opcode(24, 1)
class BeamInstLoopRecEnd(BeamInst):
    def __init__(self):
        super().__init__('loop_rec_end')

@opcode(25, 1)
class BeamInstWait(BeamInst):
    def __init__(self):
        super().__init__('wait')

@opcode(26, 2)
class BeamInstWaitTimeout(BeamInst):
    def __init__(self):
        super().__init__('wait_timeout')

@opcode(27, 4)
class BeamInstMPlus(BeamInst):
    def __init__(self):
        super().__init__('-m_plus')

@opcode(28, 4)
class BeamInstMMinus(BeamInst):
    def __init__(self):
        super().__init__('-m_minus')

@opcode(29, 4)
class BeamInstMTimes(BeamInst):
    def __init__(self):
        super().__init__('-m_times')

@opcode(30, 4)
class BeamInstMDiv(BeamInst):
    def __init__(self):
        super().__init__('-m_div')

@opcode(31, 4)
class BeamInstIntDiv(BeamInst):
    def __init__(self):
        super().__init__('-int_div')

@opcode(32, 4)
class BeamInstIntRem(BeamInst):
    def __init__(self):
        super().__init__('-int_rem')

@opcode(33, 4)
class BeamInstIntBand(BeamInst):
    def __init__(self):
        super().__init__('-int_band')

@opcode(34, 4)
class BeamInstIntBor(BeamInst):
    def __init__(self):
        super().__init__('-int_bor')

@opcode(35, 4)
class BeamInstIntBxor(BeamInst):
    def __init__(self):
        super().__init__('-int_bxor')


@opcode(36, 4)
class BeamInstBsl(BeamInst):
    def __init__(self):
        super().__init__('-int_bsl')

@opcode(37, 4)
class BeamInstBsr(BeamInst):
    def __init__(self):
        super().__init__('-int_bsr')

@opcode(38, 3)
class BeamInstBnot(BeamInst):
    def __init__(self):
        super().__init__('-int_bnot')

@opcode(39, 3)
@branch
@jumpref_op(0)
class BeamInstIsLt(BeamInst):
    def __init__(self):
        super().__init__('is_lt')

    def to_string(self, module):
        '''
        first operand: label
        second operand: reg
        third operand: atom
        '''
        return self.format(module, 'label{:d}, {}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2])
        ])

@opcode(40, 3)
@branch
@jumpref_op(0)
class BeamInstIsGe(BeamInst):
    def __init__(self):
        super().__init__('is_ge')

    def to_string(self, module):
        '''
        first operand: label
        second operand: reg
        third operand: atom
        '''
        return self.format(module, 'label{:d}, {}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2])
        ])


@opcode(41, 3)
@branch
@jumpref_op(0)
class BeamInstIsEq(BeamInst):
    def __init__(self):
        super().__init__('is_eq')

    def to_string(self, module):
        '''
        first operand: label
        second operand: reg
        third operand: atom
        '''
        return self.format(module, 'label{:d}, {}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2])
        ])

@opcode(42, 3)
@branch
@jumpref_op(0)
class BeamInstIsNe(BeamInst):
    def __init__(self):
        super().__init__('is_ne')

    def to_string(self, module):
        '''
        first operand: label
        second operand: reg
        third operand: atom
        '''
        return self.format(module, 'label{:d}, {}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2])
        ])

@opcode(43, 3)
@branch
@jumpref_op(0)
class BeamInstIsEqExact(BeamInst):
    def __init__(self):
        super().__init__('is_eq_exact')

    def to_string(self, module):
        '''
        first operand: label
        second operand: reg
        third operand: atom
        '''
        return self.format(module, 'label{:d}, {}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2])
        ])


@opcode(44, 3)
@branch
@jumpref_op(0)
class BeamInstIsNeExact(BeamInst):
    def __init__(self):
        super().__init__('is_ne_exact')

    def to_string(self, module):
        '''
        first operand: label
        second operand: reg
        third operand: atom
        '''
        return self.format(module, 'label{:d}, {}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2])
        ])

@opcode(45, 2)
@branch
@jumpref_op(0)
class BeamInstIsInteger(BeamInst):
    def __init__(self):
        super().__init__('is_integer')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(46, 2)
@branch
@jumpref_op(0)
class BeamInstIsFloat(BeamInst):
    def __init__(self):
        super().__init__('is_float')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(47, 2)
@branch
@jumpref_op(0)
class BeamInstIsNumber(BeamInst):
    def __init__(self):
        super().__init__('is_number')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(48, 2)
@branch
@jumpref_op(0)
class BeamInstIsAtom(BeamInst):
    def __init__(self):
        super().__init__('is_atom')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(49, 2)
@branch
@jumpref_op(0)
class BeamInstIsPid(BeamInst):
    def __init__(self):
        super().__init__('is_pid')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(50, 2)
@branch
@jumpref_op(0)
class BeamInstIsReference(BeamInst):
    def __init__(self):
        super().__init__('is_reference')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(51, 2)
@branch
@jumpref_op(0)
class BeamInstIsPort(BeamInst):
    def __init__(self):
        super().__init__('is_port')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(52, 2)
@branch
@jumpref_op(0)
class BeamInstIsNil(BeamInst):
    def __init__(self):
        super().__init__('is_nil')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        if isinstance(self.operands[0], BeamInteger):
            label_ref = self.operands[0].value
        else:
            label_ref = self.operands[0].index
        if isinstance(self.operands[1], BeamLiteral):
            return self.format(module, 'label{:d}, {}', [
                label_ref,
                self.operands[1].index
            ])
        else:
            return self.format(module, 'label{:d}, {}', [
                label_ref,
                module.get_value(self.operands[1])
            ])

@opcode(53, 2)
@branch
@jumpref_op(0)
class BeamInstIsBinary(BeamInst):
    def __init__(self):
        super().__init__('is_binary')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(54, 2)
@branch
@jumpref_op(0)
class BeamInstIsConstant(BeamInst):
    def __init__(self):
        super().__init__('-is_constant')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(55, 2)
@branch
@jumpref_op(0)
class BeamInstIsList(BeamInst):
    def __init__(self):
        super().__init__('is_list')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(56, 2)
@branch
@jumpref_op(0)
class BeamInstIsNonEmptyList(BeamInst):
    def __init__(self):
        super().__init__('is_nonempty_list')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(57, 2)
@branch
@jumpref_op(0)
class BeamInstIsTuple(BeamInst):
    def __init__(self):
        super().__init__('is_tuple')
    
    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(58, 3)
@branch
@jumpref_op(0)
class BeamInstTestArity(BeamInst):
    def __init__(self):
        super().__init__('test_arity')

    def to_string(self, module):
        '''First operand is a label, second a register
        '''
        return self.format(module, 'label{:d}, {}, {:d}', [
            self.operands[0].index,
            self.operands[1],
            self.operands[2].index
        ])

@opcode(59, 3)
@jumpref_op(2)
class BeamInstSelectVal(BeamInst):
    def __init__(self):
        super().__init__('select_val')

    def to_string(self, module):
        '''Convert select_val into something more readable
        '''
        # Merge list items two by two as key=>value
        cases = []
        for i in range(int(len(self.operands[2])/2)):
            cases.append((self.operands[2][i*2], self.operands[2][i*2+1]))
        switches = ', '.join(['%s => label%d' % (module.get_value(k), v.index) for k,v in cases])
        return self.format(module, '{}, label{:d}, [{}]', [
            module.get_value(self.operands[0]),
            self.operands[1].index,
            switches
        ])

@opcode(60, 3)
class BeamInstSelectTupleArity(BeamInst):
    def __init__(self):
        super().__init__('select_tuple_arity')

    def to_string(self, module):
        '''Convert select_val into something more readable
        '''
        # Merge list items two by two as key=>value
        cases = []
        for i in range(int(len(self.operands[2])/2)):
            cases.append((self.operands[2][i*2], self.operands[2][i*2+1]))
        switches = ', '.join(['%d => label%d' % (k.index, v.index) for k,v in cases])
        return self.format(module, '{} label{:d} [{}]', [
            module.get_value(self.operands[0]),
            self.operands[1].index,
            switches
        ])

@opcode(61, 1)
@jumpref_op(0)
class BeamInstJump(BeamInst):
    def __init__(self):
        super().__init__('jump')

    def to_string(self, module):
        return self.format(module, 'label{:d}', [
            self.operands[0].index
        ])

@opcode(62, 2)
class BeamInstCatch(BeamInst):
    def __init__(self):
        super().__init__('catch')

    def to_string(self, module):
        return self.format(module, '{} label{:d}', [
            self.operands[0],
            self.operands[1].index
        ])

@opcode(63, 1)
class BeamInstCatchEnd(BeamInst):
    def __init__(self):
        super().__init__('catch_end')

#
# Moving, extracting, modifying
# 

@opcode(64, 2)
class BeamInstMove(BeamInst):
    def __init__(self):
        super().__init__('move')

    def to_string(self, module):
        return self.format(module, '{}, {}', [
            module.get_value(self.operands[0]),
            module.get_value(self.operands[1])
        ])

@opcode(65, 3)
class BeamInstGetList(BeamInst):
    def __init__(self):
        super().__init__('get_list')

@opcode(66, 3)
class BeamInstGetTupleElement(BeamInst):
    def __init__(self):
        super().__init__('get_tuple_element')

    def to_string(self, module):
        '''First operand is a register, second one is an integer, third one
        is a reg.
        '''
        return self.format(module, '{}, {:d}, {}',  [
            self.operands[0],
            self.operands[1].index,
            self.operands[2]
        ])

@opcode(67, 3)
class BeamInstSetTupleElement(BeamInst):
    def __init__(self):
        super().__init__('set_tuple_element')

    def to_string(self, module):
        return self.format(module, '{}, {}, {}', [
            module.get_value(self.operands[0]),
            module.get_value(self.operands[1]),
            self.operands[2].index,
        ])

#
# Building terms
#

@opcode(68, 3)
class BeamInstPutString(BeamInst):
    def __init__(self):
        super().__init__('-put_string')

@opcode(69, 3)
class BeamInstPutList(BeamInst):
    def __init__(self):
        super().__init__('put_list')

    def to_string(self, module):
        return self.format(module, '{}, {}, {}', map(module.get_value, self.operands[:3]))

@opcode(70, 2)
class BeamInstPutTuple(BeamInst):
    def __init__(self):
        super().__init__('put_tuple')

    def to_string(self, module):
        return self.format(module, '{:d}, {}', [
            self.operands[0].index,
            self.operands[1]
        ])

@opcode(71, 1)
class BeamInstPut(BeamInst):
    def __init__(self):
        super().__init__('put')

    def to_string(self, module):
        return self.format(module, '{}', [
            module.get_value(self.operands[0])
        ])

#
# Raising errors
#

@exit_func
@opcode(72, 1)
class BeamInstBadMatch(BeamInst):
    def __init__(self):
        super().__init__('badmatch')

@exit_func
@opcode(73, 0)
class BeamInstIfEnd(BeamInst):
    def __init__(self):
        super().__init__('if_end')

@exit_func
@opcode(74, 1)
class BeamInstCaseEnd(BeamInst):
    def __init__(self):
        super().__init__('case_end')

#
# 'fun' support
#

@opcode(75, 1)
class BeamInstCallFun(BeamInst):
    def __init__(self):
        super().__init__('call_fun')

    def to_string(self, module):
        return self.format(module, '{}', [
            self.operands[0].index
        ])

@opcode(76, 3)
class BeamInstMakeFun(BeamInst):
    def __init__(self):
        super().__init__('-make_fun')

@opcode(77, 2)
@branch
@jumpref_op(0)
class BeamInstIsFunction(BeamInst):
    def __init__(self):
        super().__init__('is_function')

    def to_string(self, module):
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1])
        ])

#
# Late addition to R5
#

@opcode(78, 2)
class BeamInstCallExtOnly(BeamInst):
    def __init__(self):
        super().__init__('call_ext_only')

    def to_string(self, module):
        '''Operands:
        - literal (int)
        - import func
        '''
        return self.format(module, '{:d}, {}', [
            self.operands[0].index,
            module.get_import_str(self.operands[1].index)
        ])

#
# Binary matching (R7)
#

@opcode(79, 2)
class BeamInstBsStartMatch(BeamInst):
    def __init__(self):
        super().__init__('-bs_start_match')

@opcode(80, 5)
class BeamInstBsGetInteger(BeamInst):
    def __init__(self):
        super().__init__('-bs_get_integer')

@opcode(81, 5)
class BeamInstBsGetFloat(BeamInst):
    def __init__(self):
        super().__init__('-bs_get_float')

@opcode(82, 5)
class BeamInstBsGetBinary(BeamInst):
    def __init__(self):
        super().__init__('-bs_get_binary')

@opcode(83, 4)
class BeamInstBsSkipBits(BeamInst):
    def __init__(self):
        super().__init__('-bs_skip_bits')

@opcode(84, 2)
class BeamInstBsTestTail(BeamInst):
    def __init__(self):
        super().__init__('-bs_test_tail')


@opcode(85, 1)
class BeamInstBsSave(BeamInst):
    def __init__(self):
        super().__init__('-bs_save')

@opcode(86, 1)
class BeamInstBsRestore(BeamInst):
    def __init__(self):
        super().__init__('-bs_restore')

#
# Binary construction (R7A)
#

@opcode(87, 2)
class BeamInstBsInit(BeamInst):
    def __init__(self):
        super().__init__('-bs_init')

@opcode(88, 2)
class BeamInstBsFinal(BeamInst):
    def __init__(self):
        super().__init__('-bs_final')

@opcode(89, 5)
class BeamInstBsPutInteger(BeamInst):
    def __init__(self):
        super().__init__('bs_put_integer')

@opcode(90, 5)
class BeamInstBsPutBinary(BeamInst):
    def __init__(self):
        super().__init__('bs_put_binary')

@opcode(91, 5)
class BeamInstBsPutFloat(BeamInst):
    def __init__(self):
        super().__init__('bs_put_float')

@opcode(92, 2)
class BeamInstBsPutString(BeamInst):
    def __init__(self):
        super().__init__('bs_put_string')

    def to_string(self, module):
        return self.format(module, '{}, {}', [
            module.get_value(self.operands[0]),
            module.get_value(self.operands[1])
        ])

#
# Binary construction (R7B)
#

@opcode(93, 1)
class BeamInstBsNeedBuf(BeamInst):
    def __init__(self):
        super().__init__('-bs_need_buf')

#
# Floating point arithmetic
#

@opcode(94, 0)
class BeamInstFClearError(BeamInst):
    def __init__(self):
        super().__init__('fclearerror')

@opcode(95, 1)
class BeamInstFCheckError(BeamInst):
    def __init__(self):
        super().__init__('fcheckerror')

@opcode(96, 2)
class BeamInstFMove(BeamInst):
    def __init__(self):
        super().__init__('fmove')

@opcode(97, 2)
class BeamInstFConv(BeamInst):
    def __init__(self):
        super().__init__('fconv')

@opcode(98, 4)
class BeamInstFAdd(BeamInst):
    def __init__(self):
        super().__init__('fadd')

@opcode(99, 4)
class BeamInstFSub(BeamInst):
    def __init__(self):
        super().__init__('fsub')

@opcode(100, 4)
class BeamInstFMul(BeamInst):
    def __init__(self):
        super().__init__('fmul')

@opcode(101, 4)
class BeamInstFDiv(BeamInst):
    def __init__(self):
        super().__init__('fdiv')

@opcode(102, 3)
class BeamInstFNegate(BeamInst):
    def __init__(self):
        super().__init__('fnegate')


#
# New fun construction (R8)
#

@opcode(103, 1)
class BeamInstMakeFun2(BeamInst):
    def __init__(self):
        super().__init__('make_fun2')



#
# Try/catch/raise (R10B)
#

@opcode(104, 2)
class BeamInstTry(BeamInst):
    def __init__(self):
        super().__init__('try')

    def to_string(self, module):
        return self.format(module, '{}, label{:d}', [
            module.get_value(self.operands[0]),
            self.operands[1].index
        ])

@opcode(105, 1)
class BeamInstTryEnd(BeamInst):
    def __init__(self):
        super().__init__('try_end')

@opcode(106, 1)
class BeamInstTryCase(BeamInst):
    def __init__(self):
        super().__init__('try_case')

@opcode(107, 1)
class BeamInstTryCaseEnd(BeamInst):
    def __init__(self):
        super().__init__('try_case_end')

@opcode(108, 2)
class BeamInstRaise(BeamInst):
    def __init__(self):
        super().__init__('raise')

#
# New insts in R10B
#

@opcode(109, 6)
class BeamInstBsInit2(BeamInst):
    def __init__(self):
        super().__init__('bs_init2')

@opcode(110, 3)
class BeamInstBsBitsToBytes(BeamInst):
    def __init__(self):
        super().__init__('-bs_bits_to_bytes')

@opcode(111, 5)
class BeamInstBsAdd(BeamInst):
    def __init__(self):
        super().__init__('bs_add')
    
@opcode(112, 1)
class BeamInstApply(BeamInst):
    def __init__(self):
        super().__init__('apply')

@opcode(113, 2)
class BeamInstApplyLast(BeamInst):
    def __init__(self):
        super().__init__('apply_last')

@opcode(114, 2)
@branch
@jumpref_op(0)
class BeamInstIsBoolean(BeamInst):
    def __init__(self):
        super().__init__('is_boolean')

@opcode(115, 3)
class BeamInstIsFunction2(BeamInst):
    def __init__(self):
        super().__init__('is_function2')

#
# New bit syntax matching in R11B
#

@opcode(116, 5)
class BeamInstBsStartMatch2(BeamInst):
    def __init__(self):
        super().__init__('-bs_start_match2')

@opcode(117, 7)
class BeamInstBsGetInteger2(BeamInst):
    def __init__(self):
        super().__init__('bs_get_integer2')

@opcode(118, 7)
class BeamInstBsGetFloat2(BeamInst):
    def __init__(self):
        super().__init__('bs_get_float2')

@opcode(119, 7)
class BeamInstBsGetBinary2(BeamInst):
    def __init__(self):
        super().__init__('bs_get_binary2')


@opcode(120, 5)
class BeamInstBsSkipBits2(BeamInst):
    def __init__(self):
        super().__init__('bs_skip_bits2')

@opcode(121, 3)
class BeamInstBsTestTail2(BeamInst):
    def __init__(self):
        super().__init__('bs_test_tail2')

@opcode(122, 2)
class BeamInstBsSave2(BeamInst):
    def __init__(self):
        super().__init__('-bs_save2')

@opcode(123, 2)
class BeamInstBsRestore2(BeamInst):
    def __init__(self):
        super().__init__('-bs_restore2')


#
# New GC bifs introduced in R11B
#

@opcode(124, 5)
class BeamInstGCBif1(BeamInst):
    def __init__(self):
        super().__init__('gc_bif1')

    def to_string(self, module):
        return self.format(module, 'label{:d}, {}, {}, {}, {}', [
            self.operands[0].index,
            self.operands[1].index,
            self.operands[2].index,
            module.get_value(self.operands[3]),
            module.get_value(self.operands[4]),
        ])

@opcode(125, 6)
class BeamInstGCBif2(BeamInst):
    def __init__(self):
        super().__init__('gc_bif2')

    def to_string(self, module):
        '''Operands:
        - Label
        - Integer
        - Literal
        - reg
        - Integer
        - reg
        '''
        return self.format(module, 'label{:d}, {:d}, {}, {}, {}, {}', [
            self.operands[0].index,
            self.operands[1].index,
            module.get_import_str(self.operands[2].index),
            module.get_value(self.operands[3]),
            module.get_value(self.operands[4]),
            module.get_value(self.operands[5])
        ])

@opcode(126, 2)
class BeamInstBsFinal2(BeamInst):
    def __init__(self):
        super().__init__('-bs_final2')

@opcode(127, 2)
class BeamInstBsBitsToBytes2(BeamInst):
    def __init__(self):
        super().__init__('-bs_bits_to_bytes2')

@opcode(128, 2)
class BeamInstPutLiteral(BeamInst):
    def __init__(self):
        super().__init__('-put_literal')

@opcode(129, 2)
@branch
@jumpref_op(0)
class BeamInstIsBitStr(BeamInst):
    def __init__(self):
        super().__init__('is_bitstr')

#
# R12B
#

@opcode(130, 1)
class BeamInstBsContextToBinary(BeamInst):
    def __init__(self):
        super().__init__('-bs_context_to_binary')

@opcode(131, 3)
class BeamInstBsTestUnit(BeamInst):
    def __init__(self):
        super().__init__('bs_test_unit')

@opcode(132, 4)
class BeamInstBsMatchString(BeamInst):
    def __init__(self):
        super().__init__('bs_match_string')

    def to_string(self, module):
        return self.format(module, 'label{:d}, {}, {}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2]),
            module.get_value(self.operands[3])
        ])


@opcode(133, 0)
class BeamInstBsInitWritable(BeamInst):
    def __init__(self):
        super().__init__('bs_init_writable')

@opcode(134, 8)
class BeamInstBsAppend(BeamInst):
    def __init__(self):
        super().__init__('bs_append')

@opcode(135, 6)
class BeamInstBsPrivateAppend(BeamInst):
    def __init__(self):
        super().__init__('bs_private_append')

@opcode(136, 2)
class BeamInstTrim(BeamInst):
    def __init__(self):
        super().__init__('trim')

    def to_string(self, module):
        return self.format(module, '{:d}, {:d}', [
            self.operands[0].index,
            self.operands[1].index
        ])

@opcode(137, 6)
class BeamInstBsInitBits(BeamInst):
    def __init__(self):
        super().__init__('bs_init_bits')

@opcode(138, 5)
class BeamInstBsGetUtf8(BeamInst):
    def __init__(self):
        super().__init__('bs_get_utf8')

@opcode(139, 4)
class BeamInstBsSkipUtf8(BeamInst):
    def __init__(self):
        super().__init__('bs_skip_utf8')

@opcode(140, 5)
class BeamInstBsGetUtf16(BeamInst):
    def __init__(self):
        super().__init__('bs_get_utf16')

@opcode(141, 4)
class BeamInstBsSkipUtf16(BeamInst):
    def __init__(self):
        super().__init__('bs_skip_utf16')

@opcode(142, 5)
class BeamInstBsGetUtf32(BeamInst):
    def __init__(self):
        super().__init__('bs_get_utf32')

@opcode(143, 4)
class BeamInstBsSkipUtf32(BeamInst):
    def __init__(self):
        super().__init__('bs_skip_utf32')

@opcode(144, 3)
class BeamInstBsUtf8Size(BeamInst):
    def __init__(self):
        super().__init__('bs_utf8_size')

@opcode(145, 3)
class BeamInstBsPutUtf8(BeamInst):
    def __init__(self):
        super().__init__('bs_put_utf8')

@opcode(146, 3)
class BeamInstBsUtf16Size(BeamInst):
    def __init__(self):
        super().__init__('bs_utf16_size')

@opcode(147, 3)
class BeamInstBsPutUtf16(BeamInst):
    def __init__(self):
        super().__init__('bs_put_utf16')

@opcode(148, 3)
class BeamInstBsPutUtf32(BeamInst):
    def __init__(self):
        super().__init__('bs_put_utf32')

@opcode(149, 0)
class BeamInstOnLoad(BeamInst):
    def __init__(self):
        super().__init__('on_load')

#
# R14A
#

@opcode(150, 1)
class BeamInstRecvMark(BeamInst):
    def __init__(self):
        super().__init__('recv_mark')

@opcode(151, 1)
class BeamInstRecvSet(BeamInst):
    def __init__(self):
        super().__init__('recv_set')

@opcode(152, 7)
class BeamInstGcBif3(BeamInst):
    def __init__(self):
        super().__init__('gc_bif3')

@opcode(153, 1)
class BeamInstLine(BeamInst):
    def __init__(self):
        super().__init__('line')

    def __repr__(self):
        return 'Line(%s)' % self.operands[0]

    def to_string(self, module):
        '''Line is followed by a literal representing a line number index.
        '''
        result = module.get_lineno(self.operands[0].index)
        if result is not None:
            filename, line_no = result
            if filename is None:
                return '\t; line %d' % line_no
            else:
                return '\t; file %s line %d' % (filename, line_no)
        else:
            return ''

#
# R17
#

@opcode(154, 5)
class BeamInstPutMapAssoc(BeamInst):
    def __init__(self):
        super().__init__('put_map_assoc')

@opcode(155, 5)
class BeamInstPutMapExact(BeamInst):
    def __init__(self):
        super().__init__('put_map_exact')

@opcode(156, 2)
@branch
@jumpref_op(0)
class BeamInstIsMap(BeamInst):
    def __init__(self):
        super().__init__('is_map')

    def to_string(self, module):
        return self.format(module, 'label{:d}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1])
        ])

@opcode(157, 3)
class BeamInstHasMapFields(BeamInst):
    def __init__(self):
        super().__init__('has_map_fields')

@opcode(158, 3)
class BeamInstGetMapElements(BeamInst):
    def __init__(self):
        super().__init__('get_map_elements')

#
# R20
#

@opcode(159, 4)
@branch
@jumpref_op(0)
class BeamInstIsTaggedTuple(BeamInst):
    def __init__(self):
        super().__init__('is_tagged_tuple')

    def to_string(self, module):
        return self.format(module, 'label{:d}, {}, {}, {}', [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            self.operands[2].index,
            module.get_value(self.operands[3])
        ])

@opcode(160, 0)
class BeamInstBuildStacktrace(BeamInst):
    def __init__(self):
        super().__init__('build_stacktrace')

@opcode(161, 0)
class BeamInstRawRaise(BeamInst):
    def __init__(self):
        super().__init__('raw_raise')

@opcode(162, 2)
class BeamInstGetHd(BeamInst):
    def __init__(self):
        super().__init__('get_hd')

@opcode(163, 2)
class BeamInstGetTl(BeamInst):
    def __init__(self):
        super().__init__('get_tl')

@opcode(164, 2)
class BeamInstPutTuple2(BeamInst):
    def __init__(self):
        super().__init__('put_tuple2')

    def to_string(self, module):
        return self.format(module, "{}, {}", [
            module.get_value(self.operands[0]),
            module.get_value(self.operands[1])
        ])

@opcode(165, 3)
class BeamInstBsGetTail(BeamInst):
    def __init__(self):
        super().__init__('bs_get_tail')

    def to_string(self, module):
        return self.format(module, "{}, {}, {}", [
            module.get_value(self.operands[0]),
            module.get_value(self.operands[1]),
            self.operands[2].index
        ])

@opcode(166, 4)
class BeamInstBsStartMatch3(BeamInst):
    def __init__(self):
        super().__init__('bs_start_match3')

    def to_string(self, module):
        return self.format(module, "{}, {}, {}, {}", [
            module.get_value(self.operands[0]),
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2]),
            module.get_value(self.operands[3]),
        ])

@opcode(167, 3)
class BeamInstBsGetPosition(BeamInst):
    def __init__(self):
        super().__init__('bs_get_position')

    def to_string(self, module):
        return self.format(module, "{}, {}, {}", [
            module.get_value(self.operands[0]),
            module.get_value(self.operands[1]),
            self.operands[2].index
        ])

@opcode(168, 2)
class BeamInstBsSetPosition(BeamInst):
    def __init__(self):
        super().__init__('bs_set_position')

@opcode(169, 2)
class BeamInstSwap(BeamInst):
    def __init__(self):
        super().__init__('swap')

@opcode(170, 4)
class BeamInstBsStartMatch4(BeamInst):
    def __init__(self):
        super().__init__('bs_start_match4')

    def to_string(self, module):
        return self.format(module, "{}, {}, {}, {}", [
            module.get_value(self.operands[0]),
            self.operands[0].index,
            self.operands[2].index,
            module.get_value(self.operands[3]),
        ])

#
# OTP24
#

@opcode(171, 3)
class BeamInstMakeFun3(BeamInst):
    def __init__(self):
        super().__init__('make_fun3')

    def to_string(self, module):
        return self.format(module, "{}, {}, {}", [
            self.operands[0].index,
            module.get_value(self.operands[1]),
            module.get_value(self.operands[2]),
        ])

@opcode(172, 1)
class BeamInstInitYRegs(BeamInst):
    """init_yregs accept a list with the various Y registers to be initialized.
    """

    def __init__(self):
        super().__init__('init_yregs')

    def to_string(self, module):
        return self.format(module, '{}', [
            module.get_value(self.operands[0])
        ])

@opcode(173, 2)
class BeamInstRecvMarkerBind(BeamInst):
    def __init__(self):
        super().__init__('recv_marker_bind')

@opcode(174, 1)
class BeamInstRecvMarkerClear(BeamInst):
    def __init__(self):
        super().__init__('recv_marker_clear')

@opcode(175, 1)
class BeamInstRecvMarkerReserve(BeamInst):
    def __init__(self):
        super().__init__('recv_marker_reserve')

@opcode(176, 1)
class BeamInstRecvMarkerUse(BeamInst):
    def __init__(self):
        super().__init__('recv_marker_user')

#
# OTP25
#

@opcode(177, 6)
class BeamInstBsCreateBin(BeamInst):
    def __init__(self):
        super().__init__('bs_create_bin')

    def to_string(self, module):
        return self.format(module, '{}, {}, {}, {}, {}. {}', [
            module.get_value(self.operands[0]),
            module.get_value(self.operands[1]),
            self.operands[2].index,
            self.operands[3].index,
            module.get_value(self.operands[4]),
            module.get_value(self.operands[5])
        ])

@opcode(178, 3)
class BeamInstCallFun2(BeamInst):
    def __init__(self):
        super().__init__('call_fun2')

    def to_string(self, module):
        return self.format(module, '{}, {}, {}', [
            module.get_value(self.operands[0]),
            self.operands[1].index,
            module.get_value(self.operands[2])
        ])

@opcode(179, 0)
class BeamInstNifStart(BeamInst):
    def __init__(self):
        super().__init__('nif_start')

@opcode(180, 1)
class BeamInstBadRecord(BeamInst):
    def __init__(self):
        super().__init__('badrecord')

#
# OTP26
#

@opcode(181, 5)
class BeamInstUpdateRecord(BeamInst):
    def __init__(self):
        super().__init__('update_record')

    def to_string(self, module):
        cases = []
        for i in range(int(len(self.operands[4])/2)):
            cases.append((self.operands[4][i*2], self.operands[4][i*2+1]))
        switches = ', '.join(['%d => %s' % (k.index, module.get_value(v)) for k,v in cases])

        return self.format(module, '{}, {}, {}, {}, [{}]', [
            module.get_value(self.operands[0]),
            self.operands[1].index,
            module.get_value(self.operands[2]),
            module.get_value(self.operands[3]),
            switches
        ])

@opcode(182, 3)
class BeamInstBsMatch(BeamInst):
    def __init__(self):
        super().__init__('bs_match')


class BeamInstParser(object):
    '''BEAM instruction parser
    '''

    @staticmethod
    def parse(content):
        '''Parse a single instruction and return the corresponding object
        holding its representation.
        '''
        # Parse opcode
        inst_opcode = unpack('>B', content.read(1))[0]

        try:
            # Parse instruction operands
            return BeamInstsRegistry.inst_class(inst_opcode).parse_operands(content)
        except IndexError as op_not_found:
            traceback.print_exc()
            print(op_not_found)
            return None
