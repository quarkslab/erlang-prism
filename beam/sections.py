from io import BytesIO
from struct import unpack
from zlib import decompress

from .utils import BeamCompactTerm
from .types import BeamInteger, BeamAtom, BeamLiteral
from .ext import BeamExtTerm
from .instset import BeamInstParser


class BeamLineSection(object):

    def __init__(self, version, flags):
        self.__version = version
        self.__flags = flags
        self.__lines = []
        self.__filenames = ['invalid location']

    @property
    def filenames(self):
        return self.__filenames
    
    @property
    def lines(self):
        return self.__lines
    
    def get(self, line_index):
        if line_index < len(self.__lines):
            file_index, lineno = self.__lines[line_index]
            if file_index == 0:
                return (None, lineno)
            else:
                return (self.__filenames[file_index], lineno)
        raise IndexError
    
    def enumerate(self):
        '''Enumerate line references
        '''
        for findex, lineno in self.__lines:
            yield (self.__filenames[findex], lineno)

    def add_filename(self, filename):
        '''Add a filename to our filename list
        '''
        self.__filenames.append(filename)

    def add_line_ref(self, file_index, line):
        '''Add a line reference in our line section
        '''
        self.__lines.append((file_index, line))

    @staticmethod
    def parse(content):
        '''Parse a line section
        '''
        # First, parse line header (5 BE Uint32)
        version, flags, line_instr_count, num_line_refs, num_filenames = unpack(
            '>IIIII', content.read(5*4)
        )

        section = BeamLineSection(version, flags)

        section.add_line_ref(0,0)
        fname_index = 0


        i = 0
        while i < num_line_refs:
            term = BeamCompactTerm.read_term(content)
            if isinstance(term, BeamInteger):
                section.add_line_ref(fname_index, term.value)
                i += 1
            elif isinstance(term, BeamAtom):
                fname_index = term.index - 1
                assert fname_index < num_filenames

        for i in range(num_filenames):
            # Read filename length
            filename_length = unpack('>H', content.read(2))[0]
            filename = content.read(filename_length)
            section.add_filename(filename)

        return section
        
class BeamAtomSection(object):

    def __init__(self):
        self.__atoms = [b'module']

    def set_module_name(self, module_name):
        '''Set module name (atom #0)
        '''
        self.__atoms[0] = module_name

    def add(self, atom):
        self.__atoms.append(atom)

    def __len__(self):
        return len(self.__atoms)

    def __getitem__(self, index):
        if isinstance(index, int):
            if index < len(self.__atoms):
                return self.__atoms[index]
        raise IndexError

    @property
    def atoms(self):
        return self.__atoms

    @staticmethod
    def parse(content):
        '''Parse an atom section.
        '''
        section = BeamAtomSection()

        atoms_count = unpack('>i', content.read(4))[0]

        if atoms_count < 0:
            atoms_count = -atoms_count
            is_otp28 = True
        else:
            is_otp28 = False

        for i in range(atoms_count):
            if is_otp28:
                term = BeamCompactTerm.read_term(content)
                assert isinstance(term, BeamLiteral)
                atom_length = term.index
            else:
                atom_length = unpack('>B', content.read(1))[0]
            atom = content.read(atom_length)
            section.add(atom)

        return section

class BeamImportEntry(object):
    '''BEAM export entry
    '''
    def __init__(self, module, function, arity):
        self.__module = module
        self.__function = function
        self.__arity = arity

    @property
    def module(self):
        return self.__module
    
    @property
    def function(self):
        return self.__function
    
    @property
    def arity(self):
        return self.__arity
    
    def __repr__(self):
        return 'BeamImportEntry(module:%d, function:%d, arity:%d)' % (
            self.__module,
            self.__function,
            self.__arity
        )

class BeamImportSection(object):
    '''BEAM import section
    '''

    def __init__(self):
        self.__imports = []

    @property
    def imports(self):
        return self.__imports

    def add(self, module_index, function_index, arity):
        self.__imports.append(BeamImportEntry(
            module_index,
            function_index,
            arity
        ))

    def get(self, index):
        '''Get specific import
        '''
        if index < len(self.__imports):
            return self.__imports[index]
        raise IndexError

    @staticmethod
    def parse(content):
        '''Parse BEAM import section
        '''
        section = BeamImportSection()
        imports_count = unpack('>I', content.read(4))[0]
        for i in range(imports_count):
            module_index, function_index, arity = unpack(
                '>III', content.read(3*4)
            )
            section.add(module_index, function_index, arity)
        return section

class BeamExportEntry(object):
    '''BEAM export
    '''
    def __init__(self, name, arity, label):
        self.__name = name
        self.__arity = arity
        self.__label = label

    @property
    def name(self):
        return self.__name

    @property
    def arity(self):
        return self.__arity

    @property
    def label(self):
        return self.__label

    def __repr__(self):
        return 'BeamExportEntry(name:%d, arity:%d, label:%d)' % (
            self.__name,
            self.__arity,
            self.__label
        )

class BeamExportSection(object):
    '''BEAM export section
    '''

    def __init__(self):
        self.__exports = []

    @property
    def exports(self):
        return self.__exports

    def add(self, name, arity, label):
        self.__exports.append(BeamExportEntry(name, arity, label))

    def get(self, index):
        '''Get specific export
        '''
        if index < len(self.__exports):
            return self.__exports[index]
        raise IndexError

    @staticmethod
    def parse(content):
        '''Parse BEAM export section
        '''
        section = BeamExportSection()

        exports_count = unpack('>I', content.read(4))[0]
        for i in range(exports_count):
            export_name, arity, lbl_offset = unpack('>III', content.read(3*4))
            section.add(export_name, arity, lbl_offset)

        return section

class BeamFunctionEntry(object):
    '''BEAM function entry
    '''

    def __init__(self, func_atom, arity, offset, index, nfree, ouniq):
        self.__func_atom = func_atom
        self.__arity = arity
        self.__offset = offset
        self.__index = index
        self.__nfree = nfree
        self.__ouniq = ouniq

    @property
    def name(self):
        return self.__func_atom

    @property
    def arity(self):
        return self.__arity

    @property
    def offset(self):
        return self.__offset

    @property
    def index(self):
        return self.__index

    @property
    def nfree(self):
        return self.__nfree

    @property
    def ouniq(self):
        return self.__ouniq

    def __repr__(self):
        return 'BeamFunctionEntry(atom:%d, arity:%d, offset:%d, index:%d, nfree:%d, ouniq:%d)' % (
            self.__func_atom,
            self.__arity,
            self.__offset,
            self.__index,
            self.__nfree,
            self.__ouniq
        )

class BeamFunctionSection(object):
    '''BEAM function table
    '''

    def __init__(self):
        self.__functions = []

    def add(self, func, arity, offset, index, nfree, ouniq):
        self.__functions.append(BeamFunctionEntry(
            func, arity, offset, index, nfree, ouniq
        ))

    @property
    def functions(self):
        return self.__functions

    @staticmethod
    def parse(content):
        '''Parse function section
        '''
        section = BeamFunctionSection()

        funcs_count = unpack('>I', content.read(4))[0]

        for i in range(funcs_count):
            fun_atom_index, arity, offset, index, nfree, ouniq = unpack(
                '>IIIIII',
                content.read(6*4)
            )
            section.add(fun_atom_index, arity, offset, index, nfree, ouniq)

        return section

class BeamLiteralSection(object):
    '''BEAM Literal section
    '''

    def __init__(self):
        self.__literals = []

    def add(self, term):
        self.__literals.append(term)

    def get(self, index):
        if index < len(self.__literals):
            return self.__literals[index]
        return None

    @staticmethod
    def parse(content):
        '''Parse BEAM literal section
        '''

        section = BeamLiteralSection()

        # Read uncompressed size
        uncompressed_size = unpack('>I', content.read(4))[0]

        # Read compressed data and decompress
        compressed_data = content.getvalue()[4:]
        data = BytesIO(decompress(compressed_data))

        # Parse decompressed data
        value_count = unpack('>I', data.read(4))[0]
        for i in range(value_count):
            # Skip Uint32
            _ = data.read(4)

            # Read byte ext
            ext_term = BeamExtTerm.parse(data)

            section.add(ext_term)

        return section

class BeamCodeSection(object):
    '''BEAM code parser
    '''

    def __init__(self):
        self.__insts = []

    @property
    def insts(self):
        return self.__insts

    def add(self, inst):
        self.__insts.append(inst)

    @staticmethod
    def parse(content):
        '''Parse code section content
        '''
        # Code section
        section = BeamCodeSection()

        # Parse code version
        code_version = unpack('>I', content.read(4))[0]
  
        # Read different objects counts
        instset, highest_opcode, label_count, fun_count = unpack('>IIII', content.read(4*4))

        bytes_read = 20
        content_length = len(content.getvalue())

        # Read instructions
        insts = []
        while content.tell() < content_length:
            inst = BeamInstParser.parse(content)
            section.add(inst)

        return section
