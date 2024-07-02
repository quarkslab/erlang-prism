"""BEAM file format parser
"""
import gzip
import os
import zipfile
import traceback

from io import BytesIO
from struct import unpack
from tempfile import NamedTemporaryFile


from .exceptions import InvalidBeamHeader, UnknownBeamFileFormat
from .sections import BeamAtomSection, BeamExportSection, BeamImportSection,\
    BeamFunctionSection, BeamLineSection, BeamLiteralSection, BeamCodeSection
from .types import BeamLiteral, BeamLabel, BeamNIL, BeamAtom, BeamInteger, \
    BeamXReg, BeamYReg, BeamTypedReg, BeamExtList
from .ext import BeamListExt

class BeamFile:
    '''BEAM file format parser
    '''

    def __init__(self, f):
        '''Initialize a BeamFile object.

        @param  f   python file object
        '''
        # Save source
        self.__source = f

        # Initialize sections
        self.__length = 0
        self.__atoms = None
        self.__code = None
        self.__funcs = None
        self.__exports = None
        self.__literals = None
        self.__imports = None
        self.__line_nums = None

        # Parse beam file
        self.__parse()

    @property
    def code(self):
        """Retrieve code section.
        """
        return self.__code

    @property
    def name(self):
        """Retrieve this BEAM file name (normally stored as the first literal
        in our literal section).
        """
        return self.get_atom(1)

    def encode_literal(self, lit):
        """Encode literal to avoid line breaks.
        """
        return lit.replace('\n', '\\n').replace('\r', '\\r')

    def __parse(self):
        try:
            # Check header and read file length
            self.__check_header()

            # Iterate over chunks
            read_length = 0
            while read_length < (self.__length - 4):
                # Read 4-byte marker
                marker = self.__source.read(4)

                # Read chunk length
                chunk_length = unpack('>I', self.__source.read(4))[0]

                # Read chunk body
                chunk_body = self.__source.read(chunk_length)

                # Process chunk
                self.__decode_chunk(marker, chunk_body)

                # Align on 4-byte boundary
                next_chunk_offset = 4*(int((chunk_length + 3) / 4))
                remaining = next_chunk_offset - chunk_length
                _next_chunk_offset = next_chunk_offset + read_length + 12 + 8
                _ = self.__source.read(remaining)

                read_length += 8 + next_chunk_offset          

        except IOError as input_error:
            raise UnknownBeamFileFormat from input_error
        except InvalidBeamHeader as invalid_header:
            raise UnknownBeamFileFormat from invalid_header

    def __check_header(self):
        '''Check BEAM file header

        Raises InvalidBeamHeader if header is not valid.
        '''
        try:
            # Read file header
            header = self.__source.read(12)
            if len(header) != 12:
                print('not enough bytes')
                raise InvalidBeamHeader

            # Validate file header
            iff, length, magic = unpack('>III', header)
            assert iff == 0x464f5231
            assert magic == 0x4245414d

            # Save length
            self.__length = length
        except IOError as read_error:
            raise InvalidBeamHeader from read_error
        except AssertionError as fail:
            raise InvalidBeamHeader from fail

    def __decode_chunk(self, marker, content):
        '''Decode chunk based on chunk marker and content
        '''
        if marker == b'Line':
            self.__line_nums = BeamLineSection.parse(BytesIO(content))
        elif marker ==  b'Atom' or marker == b'AtU8':
            self.__atoms = BeamAtomSection.parse(BytesIO(content))
        elif marker == b'ImpT':
            self.__imports = BeamImportSection.parse(BytesIO(content))
        elif marker == b'ExpT':
            self.__exports = BeamExportSection.parse(BytesIO(content))
        elif marker == b'FunT':
            self.__funcs = BeamFunctionSection.parse(BytesIO(content))
        elif marker == b'LitT':
            self.__literals = BeamLiteralSection.parse(BytesIO(content))
        elif marker == b'Code':
            self.__code = BeamCodeSection.parse(BytesIO(content))

    def get_atom(self, atom_index):
        '''Get atom by index
        '''
        if isinstance(atom_index, BeamNIL):
            return 'nil'
        elif self.__atoms is not None:
            return self.__atoms[atom_index].decode('utf-8')

    def get_literal(self, literal_index):
        '''Get literal by index
        '''
        if self.__literals is not None:
            return self.__literals.get(literal_index)

    def get_lineno(self, line_index):
        '''Get line number from Line table
        '''
        if self.__line_nums is not None:
            return self.__line_nums.get(line_index)

    def get_value(self, value):
        if isinstance(value, BeamAtom):
            return "'%s'" % self.get_atom(value.index)
        elif isinstance(value, BeamInteger):
            return '0x%x' % value.value
        elif isinstance(value, BeamLabel):
            return 'label%d' % value.index
        elif isinstance(value, BeamLiteral):
            return '`%s`' % self.get_literal(value.index)
        elif isinstance(value, BeamYReg):
            return 'Y%d' % value.index
        elif isinstance(value, BeamXReg):
            return 'X%d'  % value.index
        elif isinstance(value, BeamTypedReg):
            return '{}<{}>'.format(value.register, value.typeinfo.index)
        elif isinstance(value, BeamListExt):
            contents = ', '.join([self.get_value(i) for i in value])
            return '[%s]' % contents
        elif isinstance(value, BeamExtList):
            contents = ', '.join([self.get_value(i) for i in value])
            return '[%s]' % contents

    def imports(self):
        '''List imports

        Return a list of tuples (module, function, arity) for each import
        declared in the BEAM file.
        '''
        imports = []
        if self.__imports is not None:
            for imp in self.__imports.imports:
                module_name = self.get_atom(imp.module).decode('utf-8')
                func_name = self.get_atom(imp.function).decode('utf-8')
                imports.append((
                    module_name,
                    func_name,
                    imp.arity
                ))
        return imports

    def get_import_str(self, import_index):
        '''Get import as string
        '''
        imp = self.__imports.get(import_index)
        return '<%s:%s/%d>' % (
            self.get_atom(imp.module),
            self.get_atom(imp.function),
            imp.arity
        )

    def exports(self):
        '''List exports

        Return a list of tuples (module, function, arity) for each export
        declared in the BEAM file.
        '''
        exports = []
        if self.__exports is not None:
            for exp in self.__exports.exports:
                func_name = self.get_atom(exp.name).decode('utf-8')
                exports.append((
                    func_name,
                    exp.arity
                ))
        return exports

    def local_functions(self):
        '''List functions

        Return a list of tuples (name, arity, offset, index, nfree, ouniq) for
        each declared function.
        '''
        functions = []
        if self.__funcs is not None:
            for func in self.__funcs.functions:
                name = self.get_atom(func.name)
                functions.append((
                    name,
                    func.arity,
                    func.offset,
                    func.index,
                    func.nfree,
                    func.ouniq
                ))
        return functions

    def generate_assembly(self):
        '''Process code instructions, translate operands into readable values
        and display the result.
        '''
        output = ''
        for inst in self.__code.insts:
            output += '%s\n' % inst.to_string(self)
        return output


def load_gzipped_beam(filename):
    '''Load a Gzipped BEAM file
    '''
    try:
        with gzip.open(filename, 'rb') as f:
            return BeamFile(f)
    except Exception as oops:
        traceback.print_exc()
        raise UnknownBeamFileFormat from oops

def load_beam(filename):
    """Load BEAM file from filename.
    """
    with open(filename,'rb') as f:
        # First try with normal BEAM file format
        try:
            result = BeamFile(f)
            return result
        except UnknownBeamFileFormat:
            # Maybe a gzipped beam file
            result = load_gzipped_beam(filename)
            return result

def load_beams_from_ez(filename):
    '''Load a set of beams from EZ archive.
    '''
    zfile = zipfile.ZipFile(filename)
    beams = []

    # Walk through zip file information list
    for info in zfile.infolist():
        if not info.is_dir():
            arch_path = os.path.dirname(info.filename)
            arch_file = os.path.basename(info.filename)
            arch_fp = os.path.join(arch_path, arch_file)
            if arch_file.endswith('.beam'):
                try:
                    # try to load beam file as a normal BEAM file
                    with zfile.open(arch_fp, 'r') as f:
                        beams.append(BeamFile(f))
                except UnknownBeamFileFormat:
                    try:
                        # Consider beam file as gzipped
                        with zfile.open(arch_fp, 'r') as f:
                            # Extract compressed file into a temporary file
                            content = f.read()
                            temp = NamedTemporaryFile(delete=False)
                            temp.write(content)
                            temp.close()

                            # Load beam from temporary file
                            beams.append(load_beam(temp.name))

                            # Delete temporary file
                            os.unlink(temp.name)
                    except UnknownBeamFileFormat:
                        print(f"[!] Unable to load {arch_fp}")
                        return

    # Return BEAM files
    return beams
