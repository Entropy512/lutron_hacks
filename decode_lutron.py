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

'''
This lookup table and algorithm pulled from the STM32 communication coprocessor firmware of a Caseta bridge

Based on https://ceng2.ktu.edu.tr/~cevhers/ders_materyal/bil311_bilgisayar_mimarisi/supplementary_docs/crc_algorithms.pdf - this SHOULD be getting fed two bytes of trailing zeros
but it isn't.

It appears this is a Lutron implementation mistake, or intentional to prevent easier reverse engineering

We can regenerate the CRC table in the normal fashion for precomputing one from a polynomial of 0xca0f though
''' 
lutron_crc = crcmod.mkCrcFun(0x1ca0f, 0, False, 0)
crctable = [lutron_crc(j.to_bytes()) for j in range(256)]
def calc_crc(message):
    crc_reg = 0
    for j in range(len(message)):
        crc_reg_upper = crc_reg >> 8
        crc_reg = (((crc_reg << 8) & 0xff00) + message[j]) ^ crctable[crc_reg_upper]
    return crc_reg

#This is the exact algorithm used by the STM32 communications coprocessor of the Caseta bridge
def get_pktlen_from_command(cmdbyte):
    if(cmdbyte & 0xc0 == 0):
        return 5
    elif(cmdbyte & 0xe0 == 0xa0):
        return 0x35
    else:
        return 0x18


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
        decoded_bytes = b''
        bits = bits[ofs+len(preamble_sync)-1:] #Detect and strip our preamble and sync byte, plus the start bit of our first data byte
        chunks = wrap(bits, 10) #Split our bitstream into 10-bit chunks - Every byte has 0 prepended to it and 1 appended (async serial N81)
        for chunk in chunks:
            if(chunk[0] == '0' and chunk[-1] == '1'): #make sure it's 8N1 async serial
                byteval = int(chunk[8:0:-1],2) #LSB-first, so swap bit order
                decoded_bytes += byteval.to_bytes(1)
            else:
                pass #FIXME:  Handle trailing data differently than a non-match in the middle of a sequence if there's an error
        # CRC is not calculated for sync byte or the preceding 0xFA 0xDE, it starts with the command byte
        if((decoded_bytes[0] == 0xfa) & (decoded_bytes[1] == 0xde)):
            decoded_bytes = decoded_bytes[2:] #Strip 0xFADE prefix
            pkt_end_idx = get_pktlen_from_command(decoded_bytes[0]) #Our packet length includes the 0xfade prefix
            decoded_bytes = decoded_bytes[:pkt_end_idx] #Strip trailing trash that we sometimes receive
            calculated_crc = calc_crc(decoded_bytes[:-2])
            message_crc = (decoded_bytes[-2] << 8) + decoded_bytes[-1]
            #passing a delimiter to hex() requires Python 3.8 or later
            print(decoded_bytes.hex(' ') + ' - CRC match is ' + str(calculated_crc == message_crc) + ', length is ' + str(len(decoded_bytes)))

