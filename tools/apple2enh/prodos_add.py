#!/usr/bin/env python3
"""Add files to a ProDOS-order (.po) disk image, list its volume directory,
or print a file from it. A Java-free alternative to AppleCommander for the
'disk' make goal.

usage: prodos_add.py IMAGE list
       prodos_add.py IMAGE cat NAME
       prodos_add.py IMAGE add NAME=SRC[,TYPE=hh][,AUX=hhhh] ...

SRC in AppleSingle format (cc65 output) supplies its own type and aux type.
"""
import struct
import sys

BLOCK = 512
ACCESS_RWD = 0xC3
VOLDIR = 2


class Image:
    def __init__(self, path):
        self.path = path
        self.data = bytearray(open(path, 'rb').read())
        hdr = self.block(VOLDIR)
        self.entry_len = hdr[0x23]
        self.entries_per_block = hdr[0x24]
        self.bitmap_block = struct.unpack_from('<H', hdr, 0x27)[0]
        self.total_blocks = struct.unpack_from('<H', hdr, 0x29)[0]

    def block(self, n):
        return memoryview(self.data)[n * BLOCK:(n + 1) * BLOCK]

    def save(self):
        open(self.path, 'wb').write(self.data)

    def dir_entries(self):
        blk = VOLDIR
        first = True
        while blk:
            b = self.block(blk)
            for i in range(self.entries_per_block):
                if first and i == 0:
                    continue
                yield blk, 4 + i * self.entry_len
            first = False
            blk = struct.unpack_from('<H', b, 2)[0]

    def entries(self):
        for blk, off in self.dir_entries():
            e = self.block(blk)[off:off + self.entry_len]
            if e[0] >> 4:
                yield blk, off, bytes(e)

    def is_free(self, n):
        return self.data[self.bitmap_block * BLOCK + n // 8] & (0x80 >> (n % 8)) != 0

    def mark_used(self, n):
        self.data[self.bitmap_block * BLOCK + n // 8] &= ~(0x80 >> (n % 8)) & 0xFF

    def alloc(self):
        for n in range(self.total_blocks):
            if self.is_free(n):
                self.mark_used(n)
                self.data[n * BLOCK:(n + 1) * BLOCK] = bytes(BLOCK)
                return n
        raise SystemExit('disk full')

    @staticmethod
    def name_of(e):
        return bytes(e[1:1 + (e[0] & 0x0F)]).decode('ascii')

    def read(self, name):
        for _, _, e in self.entries():
            if self.name_of(e) == name:
                break
        else:
            raise SystemExit(f'{name} not found')
        key = struct.unpack_from('<H', e, 0x11)[0]
        eof = e[0x15] | e[0x16] << 8 | e[0x17] << 16
        if e[0] >> 4 == 1:
            return bytes(self.block(key)[:eof])
        idx = self.block(key)
        out = b''
        for i in range((eof + BLOCK - 1) // BLOCK):
            out += bytes(self.block(idx[i] | idx[256 + i] << 8))
        return out[:eof]

    def add(self, name, payload, ftype, aux):
        name = name.upper()
        if any(self.name_of(e) == name for _, _, e in self.entries()):
            raise SystemExit(f'{name} already on disk')
        nblocks = max(1, (len(payload) + BLOCK - 1) // BLOCK)
        blocks = [self.alloc() for _ in range(nblocks)]
        for i, n in enumerate(blocks):
            chunk = payload[i * BLOCK:(i + 1) * BLOCK]
            self.data[n * BLOCK:n * BLOCK + len(chunk)] = chunk
        if nblocks == 1:
            storage, key, used = 1, blocks[0], 1
        elif nblocks <= 256:
            key = self.alloc()
            for i, n in enumerate(blocks):
                self.data[key * BLOCK + i] = n & 0xFF
                self.data[key * BLOCK + 256 + i] = n >> 8
            storage, used = 2, nblocks + 1
        else:
            raise SystemExit(f'{name}: tree files unsupported')
        for blk, off in self.dir_entries():
            if self.data[blk * BLOCK + off] >> 4 == 0:
                break
        else:
            raise SystemExit('volume directory full')
        e = bytearray(self.entry_len)
        e[0] = storage << 4 | len(name)
        e[1:1 + len(name)] = name.encode('ascii')
        e[0x10] = ftype
        struct.pack_into('<H', e, 0x11, key)
        struct.pack_into('<H', e, 0x13, used)
        e[0x15:0x18] = len(payload).to_bytes(3, 'little')
        e[0x1E] = ACCESS_RWD
        struct.pack_into('<H', e, 0x1F, aux)
        struct.pack_into('<H', e, 0x25, blk)
        self.data[blk * BLOCK + off:blk * BLOCK + off + self.entry_len] = e
        count_at = VOLDIR * BLOCK + 4 + 0x21
        count = struct.unpack_from('<H', self.data, count_at)[0]
        struct.pack_into('<H', self.data, count_at, count + 1)


def applesingle(raw):
    if raw[:4] != b'\x00\x05\x16\x00':
        return None
    forks = {}
    for i in range(struct.unpack_from('>H', raw, 24)[0]):
        eid, off, ln = struct.unpack_from('>III', raw, 26 + i * 12)
        forks[eid] = raw[off:off + ln]
    info = forks[11]
    return forks[1], struct.unpack_from('>H', info, 2)[0], struct.unpack_from('>I', info, 4)[0]


def main(argv):
    img = Image(argv[1])
    if argv[2] == 'list':
        for _, _, e in img.entries():
            eof = e[0x15] | e[0x16] << 8 | e[0x17] << 16
            print(f'{img.name_of(e):<16} st={e[0] >> 4} type=${e[0x10]:02X} '
                  f'aux=${struct.unpack_from("<H", e, 0x1F)[0]:04X} {eof:>7}')
        return
    if argv[2] == 'cat':
        sys.stdout.buffer.write(img.read(argv[3].upper()))
        return
    for spec in argv[3:]:
        parts = spec.split(',')
        name, src = parts[0].split('=', 1)
        raw = open(src, 'rb').read()
        payload, ftype, aux = applesingle(raw) or (raw, 0x06, 0)
        for kv in parts[1:]:
            k, v = kv.split('=')
            if k == 'TYPE':
                ftype = int(v, 16)
            elif k == 'AUX':
                aux = int(v, 16)
        img.add(name, payload, ftype, aux)
        print(f'added {name} ({len(payload)} bytes, type=${ftype:02X} aux=${aux:04X})')
    img.save()


main(sys.argv)
