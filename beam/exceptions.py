'''BEAM exceptions
'''

class UnknownBeamFileFormat(Exception):
    pass

class UnsupportedBeamCompactTerm(Exception):
    '''UnsupportedBeamCompactTerm
    '''
    pass

class InvalidBeamHeader(Exception):
    '''Invalid BEAM file header.
    '''
    pass

class UnsupportedBeamExt(Exception):
    def __init__(self, tag):
        super().__init__()
        self.tag = tag

    def __repr__(self):
        return 'UnsupportedBeamExt(%d)' % self.tag