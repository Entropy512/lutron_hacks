#!/usr/bin/env python3

from xml.etree import ElementTree as ET
from textwrap import wrap
import argparse
import crcmod

ap = argparse.ArgumentParser()
ap.add_argument('-i', '--input', required=True,
    help='path to input file')

args = vars(ap.parse_args())

tree = ET.parse(args['input'])
root = tree.getroot()

#try a bunch of CRC functions to see if one matches.  So far, all failures
crcfuncs = []
for poly in 0x18005, 0x11021:
    for init in 0x0000, 0xffff:
        for xor in 0x0000, 0xffff:
            for rev in False, True:
                crcfuncs.append([crcmod.mkCrcFun(poly, init, rev, xor) , poly, init, xor, rev])


'''
Preamble is a repeating 1010101010 sequence.
Sync is 0xff with a trailing 10.
All bytes in the Clear Connect protocol have a 10 sequence appended to them.
'''
preamble_sync = '101010101010101111111110'
msgs = root.find('messages')
for msg in msgs.iter('message'):
    bits = msg.attrib['bits']
    ofs = bits.find(preamble_sync)
    if(ofs > 0):
        decoded = ''
        decoded_bytes = b''
        decoded_bytes_msb = b''
        bits = bits[ofs+len(preamble_sync):] #Strip our preamble and the sync byte
        chunks = wrap(bits, 10) #Split our bitstream into 10-bit chunks - Every byte has 10 appended to it
        for chunk in chunks:
            if(chunk[8:] == '10'): #All valid bytes appear to have a trailing 10
                byteval = int(chunk[7::-1],2) #LSB-first, so swap bit order
                decoded += '{:02X} '.format(byteval)
                decoded_bytes += byteval.to_bytes(1)
                decoded_bytes_msb += int(chunk[:-2],2).to_bytes(1)
            else:
                pass #FIXME:  Handle trailing data differently than a non-match in the middle of a sequence if there's an error
        print(decoded)
        if(1): # FIXME:  Make this somehow configurable, but disable CRC flailing for now
            for func in crcfuncs: #Flail semi-helplessly at determining the CRC algorithm
                bdata = b'\xff' + decoded_bytes[:-2]
                print(hex(func[0](bdata)) + " " + str(func[1:]))
                print(hex(int('{:016b}'.format(func[0](bdata))[::-1], 2)) + " " + str(func[1:]))

                bdata = decoded_bytes[:-2]
                print(hex(func[0](bdata)) + " " + str(func[1:]))
                print(hex(int('{:016b}'.format(func[0](bdata))[::-1], 2)) + " " + str(func[1:]))

                bdata = decoded_bytes[2:-2]
                print(hex(func[0](bdata)) + " " + str(func[1:]))
                print(hex(int('{:016b}'.format(func[0](bdata))[::-1], 2)) + " " + str(func[1:]))

                bdata = decoded_bytes[3:-2]
                print(hex(func[0](bdata)) + " " + str(func[1:]))
                print(hex(int('{:016b}'.format(func[0](bdata))[::-1], 2)) + " " + str(func[1:]))
