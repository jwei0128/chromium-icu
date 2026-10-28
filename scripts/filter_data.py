#!/usr/bin/env python3
# Copyright 2026 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Minimal ICU common-data (.dat, 'CmnD') lister/filter, like `icupkg -l` / `icupkg -r`.

  icu_dat.py list  in.dat                     # items sorted by size
  icu_dat.py sum   in.dat                     # sizes grouped by tree (coll/, brkitr/...)
  icu_dat.py filter in.dat out.dat remove.txt # remove items matching regexes (one per line)
"""
import re
import struct
import sys


def read(path):
  d = open(path, "rb").read()
  header_size, m1, m2 = struct.unpack_from("<HBB", d, 0)
  assert (m1, m2) == (0xDA, 0x27), "not ICU data"
  assert d[12:16] == b"CmnD", d[12:16]
  toc = header_size
  (count,) = struct.unpack_from("<I", d, toc)
  entries = []
  for i in range(count):
    no, do = struct.unpack_from("<II", d, toc + 4 + 8 * i)
    end = d.index(b"\0", toc + no)
    entries.append([d[toc + no:end].decode(), do])
  offs = sorted(e[1] for e in entries) + [len(d) - toc]
  nxt = {o: offs[i + 1] for i, o in enumerate(offs[:-1])}
  items = [(n, d[toc + o:toc + nxt[o]]) for n, o in entries]
  return d[:header_size], items


def write(path, header, items):
  items = sorted(items, key=lambda x: x[0])
  count = len(items)
  names = b""
  name_offs = []
  base = 4 + 8 * count
  for n, _ in items:
    name_offs.append(base + len(names))
    names += n.encode() + b"\0"
  pos = base + len(names)
  pos += (-pos) % 16
  data = b""
  data_offs = []
  for _, blob in items:
    data_offs.append(pos + len(data))
    data += blob
    data += b"\0" * ((-len(data)) % 16)
  toc = struct.pack("<I", count)
  for no, do in zip(name_offs, data_offs):
    toc += struct.pack("<II", no, do)
  toc += names
  toc += b"\xaa" * ((-len(toc)) % 16)  # icupkg pads with 0xaa
  assert len(toc) == data_offs[0]
  open(path, "wb").write(header + toc + data)


def main():
  cmd = sys.argv[1]
  header, items = read(sys.argv[2])
  if cmd == "list":
    for n, b in sorted(items, key=lambda x: -len(x[1])):
      print(f"{len(b):9d} {n}")
  elif cmd == "sum":
    agg = {}
    for n, b in items:
      parts = n.split("/")
      k = parts[1] if len(parts) > 2 else "(root)"
      agg[k] = agg.get(k, 0) + len(b)
    for k, v in sorted(agg.items(), key=lambda x: -x[1]):
      print(f"{v / 1e6:7.3f} MB {k}")
    print(f"{sum(len(b) for _, b in items) / 1e6:7.3f} MB total, {len(items)} items")
  elif cmd == "filter":
    pats = [re.compile(l.strip()) for l in open(sys.argv[4])
            if l.strip() and not l.startswith("#")]
    kept = [(n, b) for n, b in items if not any(p.search(n) for p in pats)]
    removed = len(items) - len(kept)
    write(sys.argv[3], header, kept)
    print(f"removed {removed} items, kept {len(kept)}")


if __name__ == "__main__":
  main()
