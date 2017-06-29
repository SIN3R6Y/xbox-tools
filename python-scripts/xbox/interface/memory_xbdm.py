from .. import interface
from . import get_xbox_address
import socket
import struct
import os
import sys
import time
import importlib

(HOST, PORT) = get_xbox_address(731)
connection_timeout = 0.5


xbdm = None

def xbdm_read_line():
  data = b''
  while True:
    #print("Waiting")
    byte = xbdm.recv(1)
    #print("Got " + str(byte))
    if byte == b'\r':
      byte = xbdm.recv(1)
      assert(byte == b'\n')
      break
    data += byte
  return data

def xbdm_parse_response2(length=None):
  try:
    res = xbdm_read_line()
    if res[3] != 45: #b'-': #FIXME: I suck at python.. how to compare a single letter to a byte string element?
      raise
    status = int(res[0:3])
  except:
    return (None, None)
  if status == 200:
    return (status, res)
  if status == 201:
    return (status, str(res, encoding='ascii'))
  if status == 203:
    res = bytearray()
    assert(length != None)
    while True:
      remaining = length - len(res)
      if remaining == 0:
        break
      assert(remaining > 0)
      res += xbdm.recv(remaining)
    return (status, bytes(res))
  if status == 202:
    lines = []
    while True:
      line = xbdm_read_line()
      if line == b'.':
        return lines
      lines += [line]
    return (status, lines)
  print("Unknown status: " + str(status))
  print("from response: " + str(res))
  #FIXME: Read remaining buffer?!
  assert(False)
  return (status, res)

#FIXME: For legacy reasons, should be updated?
def xbdm_parse_response(length=None):
  return xbdm_parse_response2(length)[1]
  

def xbdm_command(cmd, length=None):
  #FIXME: If type is already in bytes we just send it binary!
  #print("Running '" + cmd + "'")
  xbdm.send(bytes(cmd + "\r\n", encoding='ascii'))
  #print("Sent")
  lines = xbdm_parse_response(length)
  #print("Done")
  return lines

def GetModules():
  return [] # FIXME: Make this work..
  lines = xbdm_command("modules")
  for line in lines:
    print(line)
    chunks = line.split()
    for chunk in chunks:
      if (chunk[0:6] == b'name=\"'):
        print("  name = '" + str(chunk[6:-1]) + "'")
      elif (chunk[0:5] == b'base='):
        print("  base = '" + str(chunk[5]) + "'")
      else:
        print('  unparsed: ' + str(chunk))
        pass
        #assert(False)
  return []
#202- multiline response follows
#name="xboxkrnl.exe" base=0x80010000 size=0x001380e0 check=0x0013eb88 timestamp=0x3cfcc86a
#name="xbdm.dll" base=0xb0011000 size=0x000620c0 check=0x0007007d timestamp=0x407c6068
#name="vx.dxt" base=0xb00b3000 size=0x00018d80 check=0x00024302 timestamp=0x407c620b
#name="wavebank.exe" base=0x00010c40 size=0x0004fa40 check=0x00000000 timestamp=0x4c14abd2 tls xbe
#.


def GetMem(addr, length):
  if False:
    cmd = "getmem addr=0x" + format(addr, 'X') + " length=0x" + format(length, 'X')
    lines = xbdm_command(cmd)
    data = bytearray()
    for line in lines:
      line = str(line, encoding='ascii').strip()
      for i in range(0, len(line) // 2):
        byte = line[i*2+0:i*2+2]
        if '?' in byte:
          print("Oops?!")
          byte = '00'
        data.append(int(byte,16))
    assert(len(data) == length)
  else:
    cmd = "getmem2 addr=0x" + format(addr, 'X') + " length=0x" + format(length, 'X')
    data = xbdm_command(cmd, length)
  return bytes(data)

def SetMem(addr, data):
  value = bytes(data)
  if True:
    cmd="setmem addr=0x" + format(addr, 'X') + " data="
    for i in range(0, len(data)):
      cmd += format(value[i], '02X')
  xbdm_command(cmd)


def delay_reconnect(reason):
  print(reason + ". Retrying in " + str(int(1000 * connection_timeout)) + " ms")
  time.sleep(connection_timeout)
  print("Retrying now")
  connect()

def connect():
  global xbdm
  while True:
    if xbdm != None:
      xbdm.close()
    try:
      xbdm = socket.create_connection((HOST, PORT), timeout=connection_timeout)
      break
    except socket.timeout:
      print("Connection timeout")
    except socket.gaierror as err:
      sys.exit("Connection error: '" + str(err) + "'")
    except ConnectionRefusedError:
      delay_reconnect("Connection refused")
    except:
      sys.exit("Unknown connection error")
  # Get login message
  try:
    (status, data) = xbdm_parse_response2()
    if status == None:
      raise
    if status != 201:
      delay_reconnect("Bad status " + str(status) + ", expected 201")
  except:
      delay_reconnect("Could not get expected response")

print("Connecting to '" + HOST + "' (Port " + str(PORT) + ")")
connect()



def read1(address, size):
  return GetMem(address, size)
def write1(address, data):
  return SetMem(address, data)

interface.read = read1
interface.write = write1

# Hack some functions so we have better read/write access
# See xbdm-hack.md for more information

hacked = False
if True:

  from ..pe import *

  modules = GetModules()
  # FIXME: Get location of xbdm.dll
  DmResumeThread_addr = resolve_export(35, image_base=0x0B0011000) #FIXME: Use location of xbdm.dll
  #DmResumeThread_addr = resolve_export(35) #FIXME: Use location of xbdm.dll
  hack = "8B5424048B1A8B4A048B4208E2028A03E203668B03E2028B03E2028803E203668903E2028903894208B80000DB02C20400"
  xbdm_command("setmem addr=0x" + format(DmResumeThread_addr, 'X') + " data=" + hack)
 
  #hack_bank = DmResumeThread_addr + (len(hack) // 2) # Put communication base behind the hack code [pretty shitty..]
  #hack_bank = 0xd0032FC0 # Works on console ?
  hack_bank = 0xD004E000 - 12 # Top of stack - works in XQEMU?!

  hacked = True
  print("Hack installed, bank at 0x" + format(hack_bank, '08X'))
  #base=0xb0011000

def xbdm_hack(address, operation, data=0):
  SetMem(hack_bank, struct.pack("<III", address, operation, data))
  xbdm_command("resume thread=0x" + format(hack_bank, 'X'))
  return GetMem(hack_bank + 8, 4)

def xbdm_read_8(address):
  return xbdm_hack(address, 1)
def xbdm_read_16(address):
  return xbdm_hack(address, 2)
def xbdm_read_32(address):
  return xbdm_hack(address, 3)

def xbdm_write_8(address, data):
  xbdm_hack(address, 4, int.from_bytes(data, byteorder='little', signed=False))
def xbdm_write_16(address, data):
  xbdm_hack(address, 5, int.from_bytes(data, byteorder='little', signed=False))
def xbdm_write_32(address, data):
  xbdm_hack(address, 6, int.from_bytes(data, byteorder='little', signed=False))

def read2(address, size):
  if hacked:
    if size == 1:
      return xbdm_read_8(address)[0:1]
    if size == 2:
      return xbdm_read_16(address)[0:2]
    if size == 4:
      return xbdm_read_32(address)[0:4]
  return GetMem(address, size)
def write2(address, data):
  if hacked:
    size = len(data)
    if size == 1:
      return xbdm_write_8(address, data)
    if size == 2:
      return xbdm_write_16(address, data)
    if size == 4:
      return xbdm_write_32(address, data)
  return SetMem(address, data)

interface.read = read2
interface.write = write2