'''Prism, a BEAM disassembler ;)
'''

import os
import sys
import argparse

from beam import load_beam, load_beams_from_ez, Beamalyzer, BeamFile
from beam.exceptions import UnknownBeamFileFormat

def search_beams(search_path: str):
    beams = []
    for root, dir, files in os.walk(search_path, topdown=True):
        for filename in files:
            filepath = os.path.join(root, filename)
            if filepath.lower().endswith('.beam'):
                try:
                    print(' - loading beam %s ...' % filename)
                    beams.append(load_beam(filepath))
                except Exception as err:
                    pass
            elif filepath.lower().endswith('.ez'):
                try:
                    print(' - loading beam pack %s ...' % filename)
                    beams.extend(load_beams_from_ez(filepath))
                except Exception as err:
                    pass
    return beams

def load_beams(filepath: str):
    try:
        if filepath.lower().endswith('.ez'):
            # Process multiple beam files contained in an EZ file
            return load_beams_from_ez(filepath)
        else:
            return [load_beam(filepath)]
    except UnknownBeamFileFormat as err:
        print('[!] Cannot parse BEAM file %s' % filepath)
        return []


def disassemble_beams(input_beams: list[BeamFile], output_dir: str):
    '''Load a single EZ file (compressed) or a single BEAM file
    '''
    # Process multiple beam files contained in an EZ file
    beams = []
    for beam in input_beams:
        print(' - analyzing module %s ...' % beam.name)
        beams.append(Beamalyzer(beam))

    processed_beams = []
    for beam in beams:
        # Process each file independently, but consider all the files
        # when solving cross-references.
        print(' - annotating module %s ...' % beam.module.name)
        beam.annotate(beams)

    # Make sure our output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Write the recovered BEAM modules into this output directory
    for beam in beams:
        beamc_path = os.path.join(output_dir, '%s.beamc' % beam.module.name)
        print('[i] Writing disassembled code from module %s to %s' % (
            beam.module.name,
            beamc_path
        ))
        with open(beamc_path, 'w') as f:
            f.write(str(beam))
            f.close()


def prism_main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o', '--output-dir',
        dest='output_dir',
        default='beamcode',
        help='Output directory'
    )
    parser.add_argument(
        '-s', '--search',
        dest='search_dir',
        help='Search this directory for BEAM files'
    )
    parser.add_argument(
        '-f', '--file',
        dest='beam_file',
        help='BEAM or EZ file to disassemble'
    )

    args = parser.parse_args()
    if args.search_dir is not None:
        print('[i] Searching directory %s ...' % args.search_dir)
        beams = search_beams(args.search_dir)
        print('[i] Found %d BEAM modules' % len(beams))
        print('[i] Disassembling ...')
        disassemble_beams(beams, args.output_dir)
    elif args.beam_file is not None:
        # Process BEAM or EZ file
        print('[i] Loading BEAM modules from %s ...' % args.beam_file)
        beams = load_beams(args.beam_file)
        print('[i] Found %d BEAM modules' % len(beams))
        print('[i] Disassembling ...')
        disassemble_beams(beams, args.output_dir)
    else:
        parser.print_help()
