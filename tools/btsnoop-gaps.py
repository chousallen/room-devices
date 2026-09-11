#!/usr/bin/env python3
# Per-connection A2DP packet-gap report from a btmon btsnoop capture (see CLAUDE.md, Bluetooth recipes).
# Usage: tools/btsnoop-gaps.py cap.btsnoop
import struct, sys, collections, datetime
f=open(sys.argv[1],'rb'); hdr=f.read(16); assert hdr[:8]==b'btsnoop\0'
datalink=struct.unpack('>I',hdr[12:16])[0]; print('datalink',datalink)  # 2001 = btmon monitor format: flags = index<<16 | opcode, opcode 6 = ACL RX
per=collections.defaultdict(collections.Counter); total=collections.Counter()
while True:
    rh=f.read(24)
    if len(rh)<24: break
    olen,ilen,flags,drops,ts=struct.unpack('>IIIIq',rh); pkt=f.read(ilen)
    if datalink==2001:
        if (flags&0xffff)!=5: continue                  # ACL RX (monitor opcode 5)
        handle=struct.unpack('<H',pkt[0:2])[0]&0x0fff
    else:
        if not (flags&1) or pkt[0]!=0x02: continue      # received ACL data only (H4)
        handle=struct.unpack('<H',pkt[1:3])[0]&0x0fff
    t=datetime.datetime(1,1,1)+datetime.timedelta(microseconds=ts, hours=8)   # btsnoop epoch 0000-01-01, shown in CST
    per[handle][(t.hour,t.minute,t.second)]+=1; total[handle]+=1
print("RX ACL packets per handle:",dict(total))
tosec=lambda s: s[0]*3600+s[1]*60+s[2]
for h,c in per.items():
    secs=sorted(c)
    print(f"\n== handle {h}: {len(secs)} s, {secs[0]} -> {secs[-1]}")
    dist=collections.Counter(c.values()); print("  pkt/s:count", ' '.join(f"{k}:{v}" for k,v in sorted(dist.items())))
    gaps=[(a,b,tosec(b)-tosec(a)-1) for a,b in zip(secs,secs[1:]) if tosec(b)-tosec(a)>1]
    print("  missing seconds:", gaps or "none")
    low=[(s,c[s]) for s in secs[1:-1] if c[s]<40]; print("  interior seconds <40 pkt/s:", low or "none")
