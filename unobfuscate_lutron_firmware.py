#!/usr/bin/env python3

#These are hardcoded for one version of the update app provided by a collaborator.  We really only need one version of coproc firmware for now anyway for our purposes
fw_start_offset = 0x06766c #0x20000 below where Ghidra loads it
fw_lens = [0x4dde6, 0x425ec, 0x53d33, 0x38d7e]

with open('lutron-coproc-firmware-update-app', 'rb') as fwapp:
    fwapp.seek(fw_start_offset)
    fw_file_idx = 0
    for flen in fw_lens:
        obsval = 0x20 #init to 0x20
        obsdata = fwapp.read(flen)
        outdata = b''
        for idx in range(len(obsdata)):
            inbyte = obsdata[idx]
            if((inbyte < 32) or (128 < inbyte)):
                outdata += inbyte.to_bytes()
            else:
                tempval = (inbyte + (0x3f - obsval)) & 0xff
                outval = (tempval + (tempval // 0x5f) * -0x5f + 0x20) & 0xff
                outdata += outval.to_bytes()
                obsval = (obsval + 1) & 0xff
                obsval = (obsval + (obsval // 0x5f) * -0x5f) & 0xff
        with open('firmware' + str(fw_file_idx) + '.s19', 'wb') as outfile:
            outfile.write(outdata)
            fw_file_idx += 1
