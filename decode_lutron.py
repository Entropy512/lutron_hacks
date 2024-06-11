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
for poly in 0x102e5,:
    for init in 0x0000,:
        for xor in 0x0000,:
            for rev in False, True:
                crcfuncs.append([crcmod.mkCrcFun(poly, init, rev, xor) , poly, init, xor, rev])

#This lookup table and algorithm pulled from the STM32 communication coprocessor firmware of a Caseta bridge
#FIXME:  Get the original CRC polynomial from this table, if it's even a normal CRC algorithm
crctable = [0, 51727, 24081, 37918, 48162, 30253, 57907, 10300, 45643, 30788, 60506, 9813, 3689, 50278, 20600, 39543, 44697, 25750, 61576, 14983, 4795, 55476, 19626, 34469, 7378,55005, 17091, 35020, 41200, 27391, 65249, 13550, 38717, 23858, 51500, 803, 11039, 57616, 29966, 48897, 9590, 61305, 31591, 45416, 39252, 21339, 51013, 3402, 14756, 62379, 26549, 44474, 34182, 20361, 56215, 4504, 35823, 16864, 54782, 8177, 14285, 64962, 27100, 41939, 58485, 11898, 47716, 28779, 22615, 37464, 1606, 52297, 22078, 39985, 2095, 49696, 59932, 8211, 46093, 32258, 19180, 32995, 5373, 57074, 63182, 15553, 43231, 25296, 63655, 12968, 42678, 27833, 17541, 36490, 6804, 53403, 29512, 47431, 11609, 59222, 53098, 1381, 37243, 23412, 49411, 2828, 40722, 21789, 32033, 46894, 9008, 59711, 56785, 6110, 33728, 18895, 25075, 44028, 16354, 62957, 28570, 42389, 12683, 64388, 54200, 6583, 36265, 18342, 741, 51434, 23796, 38651, 48839, 29896, 57558, 10969, 45230, 31393, 61119, 9392, 3212, 50819, 21149, 39058, 44156, 26227, 62061, 14434, 4190, 55889, 20047, 33856, 7735, 54328, 16422, 35369, 41493, 26650, 64516, 13835, 38360, 24535, 52169, 454, 10746, 58357, 30699, 48612, 10131, 60828, 31106, 45965, 39857, 20926, 50592, 4015, 15169, 61774, 25936, 44895, 34659, 19820, 55666, 4989, 35082, 17157, 55067, 7444, 13608, 65319, 27449, 41270, 59024, 11423, 47233, 29326, 23218, 37053, 1187, 52908, 21723, 40660, 2762, 49349, 59641, 8950, 46824, 31975, 18441, 33286, 5656, 56343, 62507, 15908, 43578, 24629, 64066, 12365, 42067, 28252, 18016, 35951, 6257, 53886, 29101, 48034, 12220, 58803, 52623, 1920, 37790, 22929, 50150, 2537, 40439, 22520, 32708, 46539, 8661, 60378, 57140, 5435, 33061, 19242, 25366, 43289, 15623, 63240, 28031, 42864, 13166, 63841, 53597, 6994, 36684, 17731]
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

