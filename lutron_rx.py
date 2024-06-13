#!/usr/bin/env python3

import spidev
import serial
import crcmod
from enum import Enum
from time import sleep

'''
This lookup table and algorithm pulled from the STM32 communication coprocessor firmware of a Caseta bridge

Based on https://ceng2.ktu.edu.tr/~cevhers/ders_materyal/bil311_bilgisayar_mimarisi/supplementary_docs/crc_algorithms.pdf - this SHOULD be getting fed two bytes of trailing zeros
but it isn't.

It appears this is a Lutron implementation mistake, or intentional to prevent easier reverse engineering

We can regenerate the CRC table in the normal fashion for precomputing one from a polynomial of 0xca0f though
''' 
lutron_crc = crcmod.mkCrcFun(0x1ca0f, 0, False, 0)
crctable = [lutron_crc(j.to_bytes(1,'little')) for j in range(256)]
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

#Receive state machine states - this is similar to Lutron's STM32 implementation
RxState = Enum('RxState', ['AWAITING_PREFIX', 'AWAITING_CMDBYTE', 'GOT_CMDBYTE'])

spi = spidev.SpiDev()
spi.open(0,0)  #SPI bus 0 device 0 on my Pi4
spi.max_speed_hz = 55700 # can probably bump this up a bit in a setup with shorter wires
'''
Set a bunch of CC1101 registers - many of these are based on https://hackaday.io/project/2291-integrated-room-sunrise-simulator/log/7223-the-wireless-interface
with some changes for async serial TX/RX
0x00 - IOCFG2 - 0x0d (async serial data out from GPIO2)
0x01 - IOCFG1 - 0x00
0x02 - IOCFG0 - 0x00
0x03 - FIFOTHR - 0x00
0x04 - SYNC1 - 0x00
0x05 - SYNC2 - 0x00
0x06 - PKTLEN - 0x00
0x07 - PKTCTRL1 - 0x00
0x08 - PKTCTRL0 - 0x32 (async serial mode, infinite packet length)
0x09 - ADDR - 0x00
0x0A - CHANNR - 0x00
0x0B - FSCTRL1 - 0x3 is default
0x0C - FSCTRL0 - 0xc0 is default
0x0D - FREQ2 - 0x10
0x0E - FREQ1 - 0xAD
0x0F - FREQ0 - 0x52
FREQ = 0x10AD52 = 433.602844 MHz

0x10 - MDMCFG4 - 0x0B : DRATE_E = 11
0x11 - MDMCFG3 - 0x3B : DRATE_M = 59
Fosc * (256 + DRATE_M) * 2^DRATE_E / 2^28 = 62484 baud

0x12 - MDMCFG2 - 0x10 : MOD_FORMAT = GFSK
0x13 - MDMCFG1 - 0x00

0x15 - DEVIATN - 0x45 : Exponent 4, Mantissa 5
Fosc * (8 + M) * 2^E / 2^17 = 41.2 kHz

0x18 - MSCM0 - 0x10 - Enable calibration when changing from IDLE to RX/TX
'''
#Reset CC1101
spi.xfer([0x30])
sleep(0.1)
#Transition CC1101 to IDLE, probably unnecessary since we should be in IDLE after reset, but better safe than sorry
spi.xfer([0x36])
spi.xfer([0x40, 0xd, 0, 0, 0, 0, 0, 0, 0, 0x32, 0, 0])
spi.xfer([0x4d, 0x10, 0xAD, 0x52, 0x0B, 0x3b, 0x10, 0x00])
spi.xfer([0x15, 0x45])
spi.xfer([0x18, 0x0c])
spi.xfer([0x40, 0xd, 0, 0, 0, 0, 0, 0, 0, 0x32, 0, 0])
spi.xfer([0x4d, 0x10, 0xAD, 0x52, 0x0B, 0x3b, 0x10, 0x00, 0x00])
spi.xfer([0x15, 0x45])
spi.xfer([0x18, 0x10])
#Transition CC1101 to RX mode
spi.xfer([0x34])

#Print out our registers for now
print([hex(j) for j in spi.xfer([0xc0] + [0] * 0x21)[1:]])

'''
Pi 4 is weird - the "Mini UART" is the primary one, and the "full featured" one is BT - opposite of most other Pis
Ubuntu doesn't have the symlinks for serial0 and serial1 that Raspbian has
FIXME:  Find a way to make this consistent on Ubuntu and Raspbian for multiple Pi models
'''
ser = serial.Serial('/dev/ttyS0', 62500)

ser.reset_input_buffer() #Flush the input buffer

#Ser up our state machine - last two bytes read and our state variable
charbuf = [b'\x00', b'\x00']
state = RxState.AWAITING_PREFIX
while(True):
    inbyte = ser.read(1)
    match state:
        case RxState.AWAITING_PREFIX:
            charbuf[0] = charbuf[1]
            charbuf[1] = inbyte
            #Our last two bytes were Lutron's prefix (0xFADE), transition our state machine
            if(charbuf[0] == b'\xfa' and charbuf[1] == b'\xde'):
                state = RxState.AWAITING_CMDBYTE
            message = b'\xfa\xde'
        case RxState.AWAITING_CMDBYTE:
            #Command byte is starting to look like a misnomer...
            pktcnt = get_pktlen_from_command(inbyte[0]) - 1
            message += inbyte
            state = RxState.GOT_CMDBYTE
        case RxState.GOT_CMDBYTE:
            # Keep receiving bytes until we get all of our packets
            pktcnt -= 1
            message += inbyte
            if(pktcnt == 0):
                calculated_crc = calc_crc(message[2:-2])
                message_crc = (message[-2] << 8) + message[-1]
                print(message.hex(' ') + ', CRC Match is ' + str(calculated_crc == message_crc))
                state = RxState.AWAITING_PREFIX