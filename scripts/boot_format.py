"""Offline AVB checks. No OEM signature is recreated; no USB access."""
import hashlib
import struct
import gzip
from Cryptodome.Hash import SHA256
from Cryptodome.PublicKey import RSA
from Cryptodome.Signature import pkcs1_15
def locate(data):
    assert data[:8]==b'ANDROID!' and data[-64:-60]==b'AVBf'
    payload_size,vb_off,vb_size=struct.unpack_from('>QQQ',data,len(data)-52)
    vb=data[vb_off:vb_off+vb_size]
    assert vb_off+vb_size<=len(data)-64 and vb[:4]==b'AVB0'
    auth_size,aux_size=struct.unpack_from('>QQ',vb,12)
    assert 256+auth_size+aux_size<=len(vb)
    assert struct.unpack_from('>I',vb,28)[0]==1  # SHA256_RSA2048
    ho,hs,so,ss,po,ps,_,_,do,ds=struct.unpack_from('>QQQQQQQQQQ',vb,32)
    assert hs==32 and ss==256 and ho+hs<=auth_size and so+ss<=auth_size
    assert po+ps<=aux_size and do+ds<=aux_size
    aux_start=256+auth_size
    descriptors=vb[aux_start+do:aux_start+do+ds]
    hashes=[]; pos=0
    while pos<len(descriptors):
        tag,size=struct.unpack_from('>QQ',descriptors,pos)
        assert size%8==0 and pos+16+size<=len(descriptors)
        if tag==2:
            e=descriptors[pos:pos+16+size]
            image_size=struct.unpack_from('>Q',e,16)[0]
            algo=e[24:56].rstrip(b'\0').decode('ascii')
            nl,sl,dl=struct.unpack_from('>III',e,56)
            assert algo=='sha256' and dl==32 and 132+nl+sl+dl<=len(e)
            name=e[132:132+nl].decode('ascii')
            hashes.append({'offset':vb_off+aux_start+do+pos,'name':name,
                           'image_size':image_size,'salt':e[132+nl:132+nl+sl],
                           'digest_offset':132+nl+sl,'digest':e[132+nl+sl:132+nl+sl+dl]})
        pos+=16+size
    assert len(hashes)==1 and hashes[0]['name']=='boot'
    page=struct.unpack_from('<I',data,36)[0]
    align=lambda n:(n+page-1)//page*page
    k,r,sec=(struct.unpack_from('<I',data,x)[0] for x in (8,16,24))
    dtbo=struct.unpack_from('<I',data,1632)[0]
    dtb=struct.unpack_from('<I',data,1648)[0]
    assert payload_size==page+align(k)+align(r)+align(sec)+align(dtbo)+align(dtb)
    assert payload_size<=vb_off
    return {'payload_size':payload_size,'offset':vb_off,'size':vb_size,
            'auth_size':auth_size,'aux_size':aux_size,'hash_offset':ho,'hash_size':hs,
            'signature_offset':so,'signature_size':ss,'key_offset':po,'key_size':ps,
            'aux_start':aux_start,'descriptor':hashes[0]}

def verify(data, expected_signature):
    m=locate(data); vb=data[m['offset']:m['offset']+m['size']]
    signed=vb[:256]+vb[m['aux_start']:m['aux_start']+m['aux_size']]
    assert hashlib.sha256(signed).digest()==vb[256+m['hash_offset']:256+m['hash_offset']+m['hash_size']]
    d=m['descriptor']
    assert d['image_size']==m['payload_size']
    assert hashlib.sha256(d['salt']+data[:d['image_size']]).digest()==d['digest']
    key=vb[m['aux_start']+m['key_offset']:m['aux_start']+m['key_offset']+m['key_size']]
    bits=struct.unpack_from('>I',key)[0]
    assert bits==2048 and len(key)==8+2*(bits//8)
    public=RSA.construct((int.from_bytes(key[8:8+bits//8],'big'),65537))
    signature=vb[256+m['signature_offset']:256+m['signature_offset']+m['signature_size']]
    valid=True
    try: pkcs1_15.new(public).verify(SHA256.new(signed),signature)
    except ValueError: valid=False
    assert valid==expected_signature
    return {'embedded_boot_hash_verified':True,'embedded_vbmeta_auth_hash_verified':True,
            'signature_valid_with_embedded_public_key':valid,
            'embedded_public_key_sha256':hashlib.sha256(key).hexdigest(),
            'oem_trust_anchor_independently_checked':False,
            'payload_size':m['payload_size'],'vbmeta_flags':struct.unpack_from('>I',vb,120)[0]}

def cpio_entries(raw):
    entries = {}; pos = 0
    while pos+110 <= len(raw):
        h=raw[pos:pos+110]
        assert h[:6] in (b'070701',b'070702')
        f=[int(h[6+i*8:14+i*8],16) for i in range(13)]
        name=raw[pos+110:pos+110+f[11]-1].decode('utf-8')
        start=(pos+110+f[11]+3)&~3; end=start+f[6]
        assert end<=len(raw)
        if name=='TRAILER!!!': break
        assert name not in entries
        entries[name]={'mode':f[1], 'uid':f[2], 'gid':f[3], 'data':raw[start:end]}
        pos=(end+3)&~3
    return entries

def boot_sections(data):
    assert data[:8]==b'ANDROID!' and struct.unpack_from('<I',data,40)[0]==2
    k,r,sec,page=(struct.unpack_from('<I',data,i)[0] for i in (8,16,24,36))
    align=lambda n:(n+page-1)//page*page
    ro=page+align(k); so=ro+align(r)
    dtbo_size,dtbo_offset=struct.unpack_from('<IQ',data,1632)
    dtb_size=struct.unpack_from('<I',data,1648)[0]
    dtb_off=so+align(sec)+align(dtbo_size)
    return {'kernel':data[page:page+k], 'ramdisk':gzip.decompress(data[ro:ro+r]),
            'second':data[so:so+sec], 'dtb':data[dtb_off:dtb_off+dtb_size],
            'recovery_dtbo':data[dtbo_offset:dtbo_offset+dtbo_size] if dtbo_size else b'',
            'header':data[:page], 'page':page,
            'cmdline':data[64:576].split(b'\0',1)[0].decode('ascii')}

def correct(data, stock):
    original=bytes(data); result=bytearray(data)
    stock_checks=verify(stock,True)
    m=locate(result); d=m['descriptor']
    struct.pack_into('>Q',result,d['offset']+16,m['payload_size'])
    at=d['offset']+d['digest_offset']
    result[at:at+32]=hashlib.sha256(d['salt']+result[:m['payload_size']]).digest()
    vb=bytes(result[m['offset']:m['offset']+m['size']])
    at_hash=m['offset']+256+m['hash_offset']
    result[at_hash:at_hash+32]=hashlib.sha256(vb[:256]+vb[m['aux_start']:m['aux_start']+m['aux_size']]).digest()
    checks=verify(bytes(result),False)
    assert checks['vbmeta_flags']==0
    assert checks['embedded_public_key_sha256']==stock_checks['embedded_public_key_sha256']
    allowed=set(range(d['offset']+16,d['offset']+24))|set(range(at,at+32))|set(range(at_hash,at_hash+32))
    assert len(original)==len(result)==33554432
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(original,result)))
    return bytes(result),checks
