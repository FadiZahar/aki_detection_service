MLLP_START_OF_BLOCK = 0x0b
MLLP_END_OF_BLOCK = 0x1c
MLLP_CARRIAGE_RETURN = 0x0d

def from_mllp(buffer):
    return str(buffer[1:-3], "ascii").split("\r") # Strip MLLP framing and final \r


def to_mllp(segments):
    m = bytes(chr(MLLP_START_OF_BLOCK), "ascii")
    m += bytes("\r".join(segments) + "\r", "ascii")
    m += bytes(chr(MLLP_END_OF_BLOCK) + chr(MLLP_CARRIAGE_RETURN), "ascii")
    return m

m1 = b'\x0bMSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240102135300||ADT^A01|||2.5\rPID|1||497030||ROSCOE DOHERTY||19870515|M\r\x1c\r'
    
m2 = b'MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5\rPID|1||125412\rOBR|1||||||20240331003200\rOBX|1|SN|CREATININE||127.5695463720204'

m3 = b'MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331035800||ADT^A03|||2.5\rPID|1||829339\r\x1c\r'

m1_a = from_mllp(m1)

m2_a = from_mllp(m2)

m3_a = from_mllp(m3)

print(m1_a)
print(m2_a)
print(m3_a)
