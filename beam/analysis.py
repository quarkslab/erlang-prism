'''BEAM module analysis
'''

from .instset import BeamInstFuncInfo, BeamInstLabel, BeamInst, BeamInstCall, \
    BeamInstCallOnly, BeamInstCallLast, BeamInstCallExt, BeamInstCallExtLast, \
    BeamInstCallExtOnly, BeamInstSelectVal, BeamInstSelectTupleArity
from .sections import BeamCodeSection
from .module import BeamFile

####################################################
# Meta-instructions
####################################################

class MetaInstSwitchCase(BeamInst):
    '''Switch case meta instruction

    This meta instruction is meant to replace `select_val` and provide a more
    readable disassembly code
    '''
    def __init__(self, tested_value, branches):
        super().__init__('switchCase')
        self.branches = branches
        self.tested_value = tested_value

    def to_string(self, module):
        '''Render a select_val instruction into a readable switch...case.
        '''
        output = 'switch(%s) {\n' % module.get_value(self.tested_value)
        for i in self.branches:
            output += 'case %s:\n' % module.get_value(i)
            block_id = self.branches[i]
            # append code block
            block = module.get_block()


class CodeBlock(object):
    '''This class represents a block of code, i.e. a set of instructions that
    starts with a label and ends when a new label is declared.
    '''

    def __init__(self, label):
        self.__label = label
        self.__insts = []
        self.__outgoing = []
        self.__ingoing = []
        self.__external = []
        self.__next = None
        self.__annotations = []

    @property
    def label(self):
        return self.__label

    @property
    def next(self):
        return self.__next

    def add_annotation(self, annotation):
        self.__annotations.append(annotation)

    def add_inst(self, inst):
        '''Add an instruction to this code block.
        '''
        self.__insts.append(inst)

    def has_in_link(self, block):
        '''Test if this code block can be reached by another block.
        '''
        return (block in self.__ingoing)

    def add_in_link(self, block):
        '''Add a new ingoing link.

        Return True if link is new, False otherwise.
        '''
        if block in self.__ingoing:
            return False
        self.__ingoing.append(block)
        return True
    
    def has_out_link(self, block):
        '''Test if this code block can reach another block.
        '''
        for inst, target in self.__outgoing:
            if target == block:
                return True
        return False

    def add_out_link(self, inst, block):
        '''Add a new outgoing link.

        Return True if link is new, False otherwise.
        '''
        if (inst, block) in self.__outgoing:
            return False
        self.__outgoing.append((inst, block))
        return True

    def add_external_ref(self, caller: str):
        '''Add an external caller
        '''
        if caller not in self.__external:
            self.__external.append(caller)

    def set_next(self, next):
        self.__next = next

    @property
    def in_refs(self):
        return self.__ingoing
    
    @property
    def out_refs(self):
        return self.__outgoing

    def is_terminal(self):
        '''Determine if this block can be the last one of the function it
        belongs to.
        '''
        for inst in self.__insts:
            if inst.is_terminal():
                return True
        return False

    def to_string(self, module):
        '''Convert code block to string
        '''
        output = ''
        
        # Add annotations first
        for annotation in self.__annotations:
            output += '%s\n' % annotation
        
        # Add external callers here
        for ext_ref in self.__external:
            output += '; => Externally called from <%s>\n' % ext_ref

        # Add internal callers here
        for in_link in self.__ingoing:
            output += '; => Called from label%d\n' % in_link
        output += 'label%d:\n' % self.label
        for inst in self.__insts:
            output += '%s\n' % inst.to_string(module)

        output += '\n'
        return output


    def __len__(self):
        return len(self.__insts)
    
    def __getitem__(self, index):
        if index < len(self.__insts):
            return self.__insts[index]
        raise IndexError


class FunctionInfo(object):
    '''This class stores some metadata associated with a specific function:
    - the function module, name and arity
    - a list of labels belonging to the function
    '''
    def __init__(self, func_info, blocks):
        # Save function information
        self.__module = func_info.operands[0].index
        self.__name = func_info.operands[1].index
        self.__arity = func_info.operands[2].index

        # Initialize a list of labels
        self.__blocks = blocks

    @property
    def blocks(self):
        return self.__blocks

    def has_block(self, block):
        '''Check if block is already associated to this function
        '''
        return block in self.__blocks

    def add_block(self, block):
        '''Assign a block to this function
        '''
        self.__blocks.append(block)


    def __repr__(self):
        labels = ', '.join(['label%d' % i for i in self.__blocks])
        return 'FunctionInfo(module:%d, name:%d, arity:%d){%s}' % (
            self.__module,
            self.__name,
            self.__arity,
            labels
        )
    
    def to_string(self, module):
        return '%s:%s/%d' % (
            module.get_atom(self.__module),
            module.get_atom(self.__name),
            self.__arity
        )

class CodeItemizer(object):
    '''Code itemizer

    This class takes a parsed BEAM file in input and split all the code in
    logical blocks (items), identified by a label and referenced in this
    class.

    Each code block is represented by an instance of `CodeBlock`, which keeps
    track of chaining information.
    '''

    def __init__(self, code_section: BeamCodeSection):
        self.__code = code_section
        self.__blocks = {}

        # Split code into identified blocks
        self.parse_code_blocks()

    def enumerate(self):
        block_ids = list(self.__blocks.keys())
        block_ids.sort()
        for block_id in block_ids:
            yield self.__blocks[block_id]


    def get_block(self, block_id):
        '''Retrieve a code block
        '''
        if block_id in self.__blocks:
            return self.__blocks[block_id]
        raise IndexError

    def parse_code_blocks(self):
        '''Transform BEAM code into a set of code blocks identified by label numbers.
        '''
        current_block = None
        for inst in self.__code.insts:
            # Do we have a label ? Then we have a code block !
            if isinstance(inst, BeamInstLabel):
                if current_block is not None:
                    self.__blocks[current_block.label] = current_block
                current_block = CodeBlock(inst.operands[0].index)
            # Is it rather an instruction ? Save it into this block.
            elif current_block is not None:
                current_block.add_inst(inst)

        # Add our last current block, if any
        if current_block is not None:
            self.__blocks[current_block.label] = current_block



class FunctionFinder(object):
    '''Function parser

    This class implements a custom algorithm to search for functions declared
    in a BEAM code section, then identify the code blocks belonging to this
    function and try to create a graph representation of its code.
    '''

    def __init__(self, itemizer):
        self.__itemizer = itemizer
        

    def find_functions(self):
        '''Identify functions from the code section and fill in metadata
        '''
        # Loop on code instructions and keep track of current label.
        # We are looking for `BeamInstFuncInfo` instructions.
        functions = []
        current_function = None
        current_labels = []
        current_block = None
        for block in self.__itemizer.enumerate():
            # Save label index as current label
            current_labels.append(block.label)
            for inst in block:
                if isinstance(inst, BeamInstFuncInfo):
                    # If we were parsing a previous function, add it to our
                    # list of discovered functions
                    if current_function is not None:
                        # Save all the labels
                        functions.append(FunctionInfo(
                            current_function,
                            current_labels[:-1]
                        ))
                        current_labels = current_labels[-1:]

                    # Set current function
                    current_function = inst

        # Save the last function (if any)
        if current_function is not None:
            # Save all the labels
            functions.append(FunctionInfo(
                current_function,
                current_labels
            ))
        return functions
    

    def graph_block(self, function, blocks, processed_blocks=None):
        '''Create a graph for a given code block.

        It will follow the execution path and create links between blocks.
        '''
        # Follow execution flow, register in/out links
        prev_block = None
        for block in blocks:
            try:
                # Takes care of default block chaining
                current_block = self.__itemizer.get_block(block)
                if prev_block is not None:
                    prev_block.set_next(current_block.label)
                
                # Look into each instruction of this block
                for inst in current_block:
                    # has the instruction some jump targets ?
                    targets = inst.jump_targets
                    if len(targets) > 0:
                        # this block redirects to another block
                        for target in targets:
                            # Is it a block not defined in the function ?
                            if not function.has_block(target):
                                print('warn: function jumps to an external block')

                            # Set xrefs
                            if current_block.add_out_link(inst, target):
                                self.graph_block(function, [target])
                            target_block = self.__itemizer.get_block(target)
                            target_block.add_in_link(current_block.label)
                
                # Block done, go on with the next one
                prev_block = current_block
            except IndexError as not_found:
                pass
        

    def graph_function(self, function: FunctionInfo):
        '''Follow flow execution for a given function and create a code block
        graph.
        '''
        # We start from the first code block of this function, that is the second
        # known code block (first one is function declaration)
        self.graph_block(function, function.blocks[1:])

class Beamalyzer(object):
    '''Main BEAM file analyzer

    This class provides:
    - a code itemizer that splits code into blocks and keeps track of links between each
    - a function finder able to list functions, associate code blocks and graph them
    - a smart disassembler able to analyze the code and produce more readable assembly code
    '''

    def __init__(self, beam_module: BeamFile):
        self.__module = beam_module
        self.__functions = None
        
        # Create our code itemizer
        self.__itemizer = CodeItemizer(self.__module.code)
        
        # Create our function finder, find functions and graph code blocks.
        self.__funcfinder = FunctionFinder(self.__itemizer)
        self.__functions = self.__funcfinder.find_functions()
        for func in self.__functions:
            self.__funcfinder.graph_function(func)

    @property
    def module(self):
        return self.__module

    @property
    def functions(self):
        return self.__functions
    
    def add_function_caller(self, function_sig, caller):
        '''Annotate our function to specify a call from an external module
        '''
        for func in self.__functions:
            current_func_sig = '<%s>' % func.to_string(self.__module)
            if current_func_sig == function_sig:
                block = self.__itemizer.get_block(func.blocks[1])
                if block is not None:
                    block.add_external_ref(caller)
                return True
        return False

        

    def __str__(self):
        '''Convert our internal code model into readable assembly code.
        '''
        output = '; Module: %s\n\n' % self.__module.name
        for block in self.__itemizer.enumerate():
            output += block.to_string(self.__module)
        return output

    def annotate(self, others=[]):
        '''Annotate code (internal xrefs mostly)
        '''
        # First, we create an associative array to map functions and their
        # first real block of code (second label).
        func_labels = {}
        for function in self.__functions:
            func_labels[function.blocks[1]] = function

        # Then we create an associtive array to map functions from other modules
        # And their corresponding objects
        mods_funcs = {}
        for mod in others:
            for func in mod.functions:
                mods_funcs['<%s>' % func.to_string(mod.module)] = mod

        # Then we walk through each code block and add xrefs
        for block in self.__itemizer.enumerate():
            # if block label matches a function, then add function info
            if block.label in func_labels:
                function = func_labels[block.label]
                block.add_annotation('; Function <%s>' % function.to_string(self.__module))

            # Annotate calls & switch...case
            for inst in block:
                if isinstance(inst, BeamInstCall) or isinstance(inst, BeamInstCallOnly) or isinstance(inst, BeamInstCallLast):
                    # Resolve first operand
                    if inst.operands[1].index in func_labels:
                        inst.add_annotation('\t; Calls %s\n' % (
                            func_labels[inst.operands[1].index].to_string(self.__module)
                        ))
                elif isinstance(inst, BeamInstCallExt) or isinstance(inst, BeamInstCallExtLast) or isinstance(inst, BeamInstCallExtOnly):
                    try:
                        # Resolve external function
                        ext_func = self.__module.get_import_str(inst.operands[1].index)
                        if ext_func in mods_funcs:
                            mod = mods_funcs[ext_func]
                            mod.add_function_caller(ext_func, function.to_string(self.__module))
                    except Exception as err_:
                        pass
                elif isinstance(inst, BeamInstSelectVal) or isinstance(inst, BeamInstSelectTupleArity):
                    # Get the list of cases=>labels
                    cases = []
                    for i in range(int(len(inst.operands[2])/2)):
                        cases.append((inst.operands[2][i*2], inst.operands[2][i*2+1]))
                    
                    # Annotate each label with the corresponding case
                    for value, label in cases:
                        case_block = self.__itemizer.get_block(label.index)
                        if case_block is not None:
                            try:
                                case_block.add_annotation('; Case {} (label{:d})'. format(
                                    self.__module.get_value(value),
                                    block.label
                                ))
                            except Exception as err:
                                pass


    def find_merging_block(self, block_a, block_b):
        '''Follow two paths starting from block A and B and look for a merging
        point.
        '''
        a_next = []
        b_next = []
        
        # Follow block A path (only next blocks)
        while block_a is not None:
            a_next.append(block_a)
            block_a = self.__itemizer.get_block(block_a).next
            
            # Exit loop if block is terminal
            if block_a.is_terminal():
                break
        
        # Follow block B path
        while block_b is not None:
            b_next.append(block_b)
            block_b = self.__itemizer.get_block(block_b).next
            # Exit loop if block is terminal
            if block_b.is_terminal():
                break
        
        # Keep same elements and return the first one
        for a in a_next:
            same = False
            for b in b_next:
                if a==b:
                    return a
        
        # No merging block, meaning each path goes its own way
        return None
