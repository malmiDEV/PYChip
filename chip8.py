from random import randint
import pygame, math, array
PC = 0x200

DISPLAY_W = 64
DISPLAY_H = 32

pygame.init() 
pygame.mixer.init(frequency=44100, size=-16, channels=1)
screen = pygame.display.set_mode((DISPLAY_W*10, DISPLAY_H*10))
pygame.display.set_caption('chip8')
pygame.display.flip()

# fetch
X   = lambda op: (op & 0x0f00) >> 8
Y   = lambda op: (op & 0x00f0) >> 4
N   = lambda op: (op & 0x000f) 
NN  = lambda op: (op & 0x00ff) 
NNN = lambda op: (op & 0x0fff)
def I(op):
   if op >= 0x8000 and op <= 0x9fff:
      return op & 0xf00f
   elif op >= 0xe000:
      return op & 0xf0ff
   else:
      return (op & 0xf000) >> 12

class Emu:
   def __init__(self):
      self.font = [
         0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
         0x20, 0x60, 0x20, 0x20, 0x70, # 1
         0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
         0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
         0x90, 0x90, 0xF0, 0x10, 0x10, # 4
         0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
         0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
         0xF0, 0x10, 0x20, 0x40, 0x40, # 7
         0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
         0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
         0xF0, 0x90, 0xF0, 0x90, 0x90, # A
         0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
         0xF0, 0x80, 0x80, 0x80, 0xF0, # C
         0xE0, 0x90, 0x90, 0x90, 0xE0, # D
         0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
         0xF0, 0x80, 0xF0, 0x80, 0x80, # F
      ]
      self.registers = [0] * 16
      self.ram = bytearray(4096)
      self.stack = [0] * 16
      self.buffer = bytearray(DISPLAY_W*DISPLAY_H)
      self.draw = False
      self.i = 0
      self.delay_timer = 0
      self.sound_timer = 0
      self.sp = 0
      self.pc = 0
      self.key = bytearray(16)
      
      self.fps = 400
      self.fps_interval = 0
      self.start_time = 0
      self.now = 0
      self.then = 0 
      self.elapsed = 0  
      
      self.running = True

      self.INSTRUCTION_SET = {
         0x00E0   : self.op_00E0,
         0x00EE   : self.op_00EE,
         0x1      : self.op_1NNN,
         0x2      : self.op_2NNN,
         0x3      : self.op_3XNN,
         0x4      : self.op_4XNN,
         0x5      : self.op_5XY0,
         0x6      : self.op_6XNN,
         0x7      : self.op_7XNN,
         0x8000   : self.op_8XY0,
         0x8001   : self.op_8XY1,
         0x8002   : self.op_8XY2,
         0x8003   : self.op_8XY3,
         0x8004   : self.op_8XY4,
         0x8005   : self.op_8XY5,
         0x8006   : self.op_8XY6,
         0x8007   : self.op_8XY7,
         0x800E   : self.op_8XYE,
         0x9000   : self.op_9XY0,
         0xA      : self.op_ANNN,
         0xB      : self.op_BNNN,
         0xC      : self.op_CXNN,
         0xD      : self.op_DXYN,
         0xE09E   : self.op_EX9E,
         0xE0A1   : self.op_EXA1,
         0xF007   : self.op_FX07,
         0xF00A   : self.op_FX0A,
         0xF015   : self.op_FX15,
         0xF018   : self.op_FX18,
         0xF01E   : self.op_FX1E,
         0xF029   : self.op_FX29,
         0xF033   : self.op_FX33,
         0xF055   : self.op_F055,
         0xF065   : self.op_FX65,
      }
      
   def init(self):
      # initialize timer
      self.fps_interval = 1000 / self.fps
      self.then = pygame.time.get_ticks()
      self.start_time = self.then

      # set program counter
      self.pc = PC

      # load font
      for i, c in enumerate(self.font):
         self.ram[i] = c

   def write(self, addr: int, val: int):
      self.ram[addr] = val

   def read(self, addr: int) -> int:
      return self.ram[addr]

   def read_word(self, addr: int) -> int:
      return self.read(addr) << 8 | self.read(addr+1)

   def increment_pc(self):
      self.pc += 2

   def skip_inst(self):
      self.pc += 4

   def load_rom(self, path: str):
      with open(path, 'rb') as f:
         data = f.read()
         for i, b in enumerate(data):
            self.write(PC + i, b)

   def execute(self, inst, args):
      if inst not in self.INSTRUCTION_SET:
         raise NotImplementedError('err inst: 0x{} args: {}'.format(inst, args))
      self.INSTRUCTION_SET.get(inst)(*args)

   def cycle(self):
      word = self.read_word(self.pc)
      inst, args = self.decode(word)
      self.execute(inst, args)
      
   def timer_update(self):
      if self.delay_timer > 0:
         self.delay_timer -= 1
      if self.sound_timer > 0:
         self.beep()
         self.sound_timer -= 1
         
   def key_handler(self):
      for event in pygame.event.get():
         if event.type == pygame.QUIT:
            self.running = False
         if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_0:      self.key[0x0] = 1
            if event.key == pygame.K_1:      self.key[0x1] = 1
            if event.key == pygame.K_2:      self.key[0x2] = 1
            if event.key == pygame.K_3:      self.key[0x3] = 1
            if event.key == pygame.K_4:      self.key[0x4] = 1
            if event.key == pygame.K_5:      self.key[0x5] = 1
            if event.key == pygame.K_6:      self.key[0x6] = 1
            if event.key == pygame.K_7:      self.key[0x7] = 1
            if event.key == pygame.K_8:      self.key[0x8] = 1
            if event.key == pygame.K_9:      self.key[0x9] = 1
            if event.key == pygame.K_a:      self.key[0xA] = 1
            if event.key == pygame.K_b:      self.key[0xB] = 1
            if event.key == pygame.K_c:      self.key[0xC] = 1
            if event.key == pygame.K_d:      self.key[0xD] = 1
            if event.key == pygame.K_e:      self.key[0xE] = 1
            if event.key == pygame.K_f:      self.key[0xF] = 1
            if event.key == pygame.K_ESCAPE: self.running = False
         if event.type == pygame.KEYUP:
            for i in range(0, 16):
               self.key[i] = 0

   def display(self):
      if self.draw:
         for j in range(0, DISPLAY_H):
            for i in range(0, DISPLAY_W):
               pixel = pygame.Rect(i*10,j*10,10,10)
               color = (0x83,0xa5,0x98) if self.buffer[j * DISPLAY_W + i] else (0x28,0x28,0x28)
               pygame.draw.rect(screen, color, pixel)
         pygame.display.flip()
   
   def beep(self):
      freq = 400
      volume = 0.05
      duration = 0.05
      sample_rate = 44100
      n = int(sample_rate * duration)
      amp = int(volume * 0x8000)
      buffer = array.array("h")
      for i in range(n):
         t = i / sample_rate
         sample = amp if math.sin(2 * math.pi * freq * t) >= 0 else -amp
         buffer.append(sample)
      sound = pygame.mixer.Sound(buffer)
      if not pygame.mixer.get_busy():
         sound.play()

   def decode(self, op: bytes) -> tuple:
      if op in [0x00e0, 0x00ee]:                # special case
         return (op, tuple())
      inst = I(op)
      if inst in [0x0, 0x1, 0x2, 0xa, 0xb]:     # nnn
         args = (NNN(op),)
      elif inst in [0x3, 0x4, 0x6, 0x7, 0xc]:   # x, nn
         args = (X(op), NN(op))
      elif inst == 0x5:                         # x, y
         args = (X(op), Y(op))
      elif inst >= 0x8000 and inst <= 0x9000:
         args = (X(op), Y(op))
      elif inst == 0xd:                         # x, y, n
         args = (X(op), Y(op), N(op))
      elif inst >= 0xe:                         # x
         args = (X(op),)

      return inst, args
   
   def run(self, path: str):
      self.init()
      self.load_rom(path)
      while self.running:
         self.now = pygame.time.get_ticks()
         self.elapsed = self.now - self.then
         if self.elapsed >= self.fps_interval:
            self.key_handler()
            self.cycle()
            self.timer_update()
            self.display()
            # print(f'PC: {hex(self.pc)}, SP: {hex(self.sp)}, I: {hex(self.i)}, INSTRUCTION: {hex(self.read_word(self.pc))}, REG: {[hex(self.registers[i]) for i in range(0,0xf)]}')
            self.then = self.now
      pygame.quit()
      
   """ 
      Chip8 CPU Instruction set implementation
      It's super unreadable but works, kinda.
   """ 
   def op_00E0(self):
      self.buffer = bytearray(DISPLAY_W*DISPLAY_H)
      self.draw = True
      self.increment_pc()
   def op_00EE(self):
      self.sp -= 1
      self.pc = self.stack[self.sp]
      self.increment_pc()
   def op_1NNN(self, addr: int):
      self.pc = addr
   def op_2NNN(self, addr: int):
      self.stack[self.sp] = self.pc
      self.sp += 1
      self.pc = addr
   def op_3XNN(self, X: bytes, addr: int):
      if self.registers[X] == addr:
         self.skip_inst()
      else:
         self.increment_pc()
   def op_4XNN(self, X: bytes, addr: int):
      if self.registers[X] != addr:
         self.skip_inst()
      else:
         self.increment_pc()
   def op_5XY0(self, X: bytes, Y: bytes):
      if self.registers[X] == self.registers[Y]:
         self.skip_inst()
      else:
         self.increment_pc()
   def op_6XNN(self, X: bytes, addr: int):
      self.registers[X] = addr
      self.increment_pc()
   def op_7XNN(self, X: bytes, addr: int):
      self.registers[X] = (self.registers[X] + addr) & 0xff
      self.increment_pc()
   def op_8XY0(self, X: bytes, Y: bytes):
      self.registers[X] = self.registers[Y]
      self.increment_pc()
   def op_8XY1(self, X: bytes, Y: bytes):
      self.registers[X] |= self.registers[Y]
      self.increment_pc()
   def op_8XY2(self, X: bytes, Y: bytes):
      self.registers[X] &= self.registers[Y]
      self.increment_pc()
   def op_8XY3(self, X: bytes, Y: bytes):
      self.registers[X] ^= self.registers[Y]
      self.increment_pc()
   def op_8XY4(self, X: bytes, Y: bytes):
      val = self.registers[X] + self.registers[Y]
      self.registers[0xf] = 1 if val > 0xff else 0
      self.registers[X] = val & 0xff
      self.increment_pc()
   def op_8XY5(self, X: bytes, Y: bytes):
      self.registers[0xf] = 1 if (self.registers[X] > self.registers[Y]) else 0
      self.registers[X] = (self.registers[X] - self.registers[Y]) & 0xff
      self.increment_pc()
   def op_8XY6(self, X: bytes, Y: bytes):
      self.registers[0xf] = self.registers[X] & 1
      self.registers[X] = (self.registers[X] >> 1) & 0xff
      self.increment_pc()
   def op_8XY7(self, X: bytes, Y: bytes):
      self.registers[0xf] = 1 if (self.registers[Y] > self.registers[X]) else 0
      self.registers[X] = (self.registers[Y] - self.registers[X]) & 0xff
      self.increment_pc()
   def op_8XYE(self, X: bytes, Y: bytes):
      self.registers[0xf] = 1 if self.registers[X] & 0x80 != 0 else 0
      self.registers[X] = (self.registers[X] << 1) & 0xff
      self.increment_pc()
   def op_9XY0(self, X: bytes, Y: bytes):
      if self.registers[X] != self.registers[Y]:
         self.skip_inst()
      else:
         self.increment_pc()
   def op_ANNN(self, addr: int):
      self.i = addr
      self.increment_pc()
   def op_BNNN(self, addr):
      self.pc = self.registers[0] + addr
   def op_CXNN(self, X: bytes, addr: bytes):
      self.registers[X] = randint(0, 0xff) & addr
      self.increment_pc()
   def op_DXYN(self, X: bytes, Y: bytes, n: bytes):
      self.registers[0xf] = 0
      for row in range(0, n):
         ypos = self.registers[Y] % 32 + row
         if ypos >= 32:
            break
         pixel = self.read(self.i + row)
         for col in range(0, 8):
            if pixel & (0x80 >> col) != 0:
               xpos = self.registers[X] % 64 + col
               self.buffer[ypos * DISPLAY_W + xpos] ^= 1
               if self.buffer[ypos * DISPLAY_W + xpos] == 0:
                  self.registers[0xf] = 1
               if xpos >= 64:
                  break
      self.draw = True
      self.increment_pc()
   def op_EX9E(self, X: bytes):
      key = self.key[self.registers[X]]
      if key == 1:
         self.skip_inst()
      else:
         self.increment_pc()
   def op_EXA1(self, X: bytes):
      key = self.key[self.registers[X]]
      if key != 1:
         self.skip_inst()
      else:
         self.increment_pc()
   def op_FX07(self, X: bytes):
      self.registers[X] = self.delay_timer
      self.increment_pc()
   def op_FX0A(self, X):
      press = False
      key = 0
      for i in range(0,16):
         if self.key[i] != 0:
            key = i
            press = True
         if not press:
            self.pc -= 2
         else:
            if self.key[key] != 0:
               self.pc -= 2
            else:
               self.registers[X] = key
               key = 0
               press = False
      self.increment_pc()
   def op_FX15(self, X: bytes):
      self.delay_timer = self.registers[X]
      self.increment_pc()
   def op_FX18(self, X: bytes):
      self.sound_timer = self.registers[X]
      self.increment_pc()
   def op_FX1E(self, X: bytes):
      self.i += self.registers[X] 
      self.increment_pc()
   def op_FX29(self, X: bytes):
      self.i = self.registers[X] * 5
      self.increment_pc()
   def op_FX33(self, X: bytes):
      x = self.registers[X]
      h = x // 100
      t = (x % 100) // 10
      o = x % 10
      self.write(self.i, h)
      self.write(self.i + 1, t)
      self.write(self.i + 2, o)
      self.increment_pc()
   def op_F055(self, X: bytes):
      for i in range(0, X + 1):
         self.write(self.i, self.registers[i])
         self.i += 1
      self.increment_pc()
   def op_FX65(self, X: bytes):
      for i in range(0, X + 1):
         self.registers[i] = self.read(self.i)
         self.i += 1
      self.increment_pc()

emu = Emu()
emu.run("roms/Brix.ch8")
