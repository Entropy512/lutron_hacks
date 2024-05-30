Initial attempts at reverse engineering Lutron's "Clear Connect" protocol using an SDR receiver.

My sample data is too large to include in this repo, so I'll publish my settings for URH ( https://github.com/jopohl/urh ) here, along with the demodulated .proto.xml files here.  A Python script that can extract the bytes from each message is included here, and has some notes on the protocol in its comments.  The input file for this script is one of URH's ".proto.xml" protocol files.

https://hackaday.io/project/2291-integrated-room-sunrise-simulator/log/7223-the-wireless-interface contains a lot of great info that was the starting point of my work, including the CC1150 register settings used by a Pico remote.  Also see https://github.com/CTeady/IRIS/tree/master/WirelessAnalysis from the same author

| Parameter | Value |
| :------ | ------: |
| Center Frequency | 433.602844 MHz |
| Data Rate | 62.4847 KBaud |
| Modulation | GFSK |

Pico remotes also send a "pre-squawk" with a constant bit value of 1.  I suspect this to be the reason ceady saw the frequency registers being altered midway through transmission.  Lamp units don't send this.  Pico remotes have a varying number of trailing zeroes after the end of a packet, lamp units have a number of trailing ones.  This probably means nothing other than slight differences in radio chipset.

URH project settings are as follows:
| Setting | Value |
| :------ | -----: |
| Sample Rate | 2 MSPS |
| Frequency | 433.603M |
| Bandwidth | 2.0 MHz |
| Default Gain | 20 |

I should be reducing the bandwidth significantly to get better SNR.  The sample rate happens to be 32 times the baud rate - which is interesting because URH is set to 64 samples per symbol...

URH demodulation settings in the Interpretation tab:
| Setting | Value |
| :------ | ----: |
| Noise | 0.05 |
| Center | -0.02 |
| Samples/Symbol | 64 |
| Error Tolerance | 1 |
| Modulation | FSK |
| Bits/Symbol | 1 |

Packets are sent as follows:
- First, a preamble of alternating 10 bits is sent.  The number varies here from one device to another, I have yet to determine the minimum.
- After the preample, all bytes are sent LSB-first with a 10 sequence appended to them.  For example, 0x01 will be sent as 1000000010, 0xFF will be sent as 1111111110
- These bytes are structured as follows for a basic "control packet".  Pairing requests are significantly longer.  There does not appear to be a length field, packet length appears to be derived from the command byte value.

| Byte(s) | Meaning/Value |
| :---- | ----: |
| 0 | Always 0xFA |
| 1 | Always 0xDE |
| 2 | Packet Type |
| 3 | Sequence Number |
| 4-7 | Device ID/Address |
| 8-12 | ??????? |
| 13 | Value? |
| 14-23 | 0xCC for broadcast |
| 14-17 | Target address for unicast |
| 18-23 | ???? for unicast |
| 24-25 | 16-bit CRC |

Sequence number always increases by 6 within a sequence.  It is unknown why this difference is 6 and not 1 - There is a suspicion this may be related to Clear Connect's timeslots, but then I would expect to see offsets as the transmitter chooses a random timeslot?

Strangely, for a "dim up" status from a lamp unit, the Packet Type changes as the value increases.  For example, starting at 0x88 when value is 0x0f, increasing by 1 for each press of the dim-up button, up to 0x8B when value is 0x83

"On" and "Off" commands do not appear to use the Byte 13 value field - instead using Byte 12.

When repeating a command (long press of a button), Pico remotes will send it as "unicast" with the same destination address as the source.

My dim-up remote captures appear corrupted, or the Pico does something weird when sending a dim-up command...

The CRC algorithm doesn't seem to match any known CRC16 variant I've tried so far.  Although I have not tried including the sync byte as part of the CRC...

