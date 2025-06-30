import asyncio
import random
import signal

from asyncio_mqtt import Client as MQTTClient, MqttError
from bleak import BleakClient

DEVICE_ADDRESS = "BE:16:FA:00:03:7A"
CHAR_UUID      = "0000fff3-0000-1000-8000-00805f9b34fb"

MQTT_BROKER = "localhost"
MQTT_TOPIC  = "led_curtain/mode"

ROWS, COLS  = 20, 20
HALF_COLS   = COLS // 2
FPS         = 4

stop_event = asyncio.Event()
mode       = "Тетрис"  # начальный режим

# Стартовые команды для инициализации шторы
INIT_CMDS = [
    bytearray.fromhex("7e075100ffffff00ef"),
    bytearray.fromhex("7e07580000ffff00ef"),
    bytearray.fromhex("7e07640101e00000" + "ff"*70 + "ef"),
]

# Управляющие команды по ключу (MQTT payload)
CONTROL_COMMANDS = {
    "Вкл":       bytearray.fromhex("7e0704ff00010201ef"),
    "Выкл":      bytearray.fromhex("7e07040000000201ef"),
    "Синий":     bytearray.fromhex("7e0705030000ff10ef"),
    "Бирюзовый": bytearray.fromhex("7e07050300ffff10ef"),
    "Зеленый":   bytearray.fromhex("7e07050300ff0010ef"),
    "Красный":   bytearray.fromhex("7e070503ff000010ef"),
    "Фиолетовый":bytearray.fromhex("7e070503ff00ff10ef"),
    "Белый":     bytearray.fromhex("7e070503ffffff10ef"),
    "Жёлтый":    bytearray.fromhex("7e070503ffff0010ef"),
    "Розовый":   bytearray.fromhex("7e070503ff008010ef"),
}

COLOR_PALETTE = [
    (20,   0,   80),
    (56,   0,  145),
    (57,   0,   98),
    (108,  0,  142),
    (180,  0,   82),
    (95,  24,   13),
]
COLOR_BLACK = (0, 0, 0)

def signal_handler():
    stop_event.set()

def rgb_to_hex_str(rgb):
    return ''.join(f"{c:02x}" for c in rgb)

def build_command_from_pixels(pixels):
    cmds = []
    i = 0
    while i < len(pixels):
        chunk = pixels[i:i+10]
        body = ""
        for r, c, col in chunk:
            body += f"{r:02x}{c:02x}{rgb_to_hex_str(col)}"
        body += "ffffffffff" * (10 - len(chunk))
        cmds.append(bytearray.fromhex("7e0764" + body + "ef"))
        i += 10
    return cmds

async def send_commands(client, commands):
    for cmd in commands:
        await client.write_gatt_char(CHAR_UUID, cmd, response=False)

async def send_control_command(client, key):
    cmd = CONTROL_COMMANDS.get(key)
    if cmd:
        await client.write_gatt_char(CHAR_UUID, cmd, response=False)

async def enter_per_led_mode(client):
    for cmd in INIT_CMDS:
        await send_commands(client, [cmd])
        await asyncio.sleep(0.05)

# ---------------- TETRIS GAME ----------------

TETROMINOS = {
    'I': [(0,0),(1,0),(2,0),(3,0)],
    'O': [(0,0),(0,1),(1,0),(1,1)],
    'T': [(0,1),(1,0),(1,1),(1,2)],
    'S': [(0,1),(0,2),(1,0),(1,1)],
    'Z': [(0,0),(0,1),(1,1),(1,2)],
    'J': [(0,0),(1,0),(2,0),(2,1)],
    'L': [(0,1),(1,1),(2,0),(2,1)],
}

class TetrisGame:
    def __init__(self, cs, cc):
        self.cols_start, self.cols_count = cs, cc
        self.field       = [[False]*cc for _ in range(ROWS)]
        self.color_field= [[COLOR_BLACK]*cc for _ in range(ROWS)]
        self.locked     = 0
        self.spawn_new_piece()

    def spawn_new_piece(self):
        self.piece = random.choice(list(TETROMINOS.keys()))
        self.blocks= TETROMINOS[self.piece][:]
        self.row  = -2
        self.col  = self.cols_count//2-2
        self.color= random.choice(COLOR_PALETTE)
        # Проверка Game Over
        for r,c in self.blocks:
            if 0<= self.row+r < ROWS and self.field[self.row+r][self.col+c]:
                self.reset_game(); break

    def reset_game(self):
        self.field = [[False]*self.cols_count for _ in range(ROWS)]
        self.color_field= [[COLOR_BLACK]*self.cols_count for _ in range(ROWS)]
        self.locked = 0
        self.spawn_new_piece()

    def can_move(self, dr, dc):
        for r,c in self.blocks:
            nr, nc = self.row+r+dr, self.col+c+dc
            if nr>=ROWS or nc<0 or nc>=self.cols_count or (nr>=0 and self.field[nr][nc]):
                return False
        return True

    def lock_piece(self):
        for r,c in self.blocks:
            nr, nc = self.row+r, self.col+c
            if 0<=nr<ROWS: 
                self.field[nr][nc]=True
                self.color_field[nr][nc]=self.color
        self.locked+=1; self.clear(); self.spawn_new_piece()

    def clear(self):
        new_f, new_c, lines = [], [], 0
        for i in range(ROWS):
            if all(self.field[i]): lines+=1
            else:
                new_f.append(self.field[i]); new_c.append(self.color_field[i])
        for _ in range(lines):
            new_f.insert(0,[False]*self.cols_count)
            new_c.insert(0,[COLOR_BLACK]*self.cols_count)
        self.field, self.color_field = new_f, new_c

    def rotate(self):
        if self.piece=='O': return
        nb=[(-c,r) for r,c in self.blocks]
        if all(0<=self.row+r<ROWS and 0<=self.col+c<self.cols_count and not self.field[self.row+r][self.col+c] for r,c in nb):
            self.blocks=nb

    def update(self):
        if self.can_move(0,1) and sum(self.field[r][self.col+max(c for r,c in self.blocks)+1] for r in range(ROWS)) < \
           sum(self.field[r][self.col-1] for r in range(ROWS)):
            self.col+=1
        else:
            self.col-=1 if self.col>0 else 0
        if random.random()<0.3: self.rotate()
        if self.can_move(1,0): self.row+=1
        else: self.lock_piece()

    def render(self, mat):
        for r in range(ROWS):
            for c in range(self.cols_count):
                mat[r+1][c+self.cols_start+1] = self.color_field[r][c] if self.field[r][c] else COLOR_BLACK
        for r,c in self.blocks:
            rr,cc = self.row+r+1, self.col+c+self.cols_start+1
            if 0<=rr<ROWS+2 and 0<=cc<COLS+2: mat[rr][cc]=self.color

# ---------------- MQTT Handler ----------------

async def mqtt_handler(client_ble):
    global mode
    try:
        async with MQTTClient(MQTT_BROKER) as client_mqtt:
            async with client_mqtt.unfiltered_messages() as msgs:
                await client_mqtt.subscribe(MQTT_TOPIC)
                async for msg in msgs:
                    payload = msg.payload.decode()
                    print("MQTT→", payload)
                    if payload == "Тетрис":
                        mode = "Тетрис"
                    elif payload in CONTROL_COMMANDS:
                        mode = "Control"
                        await send_control_command(client_ble, payload)
    except MqttError as e:
        print("MQTT error:", e)

# ---------------- Game Loop ----------------

async def game_loop(client_ble):
    global mode
    game1 = TetrisGame(0, HALF_COLS)
    game2 = None
    mat_prev = [[COLOR_BLACK]*(COLS+2) for _ in range(ROWS+2)]

    while not stop_event.is_set():
        if mode == "Тетрис":
            # обновляем и рендерим
            game1.update()
            if game1.locked>=10 and not game2:
                game2 = TetrisGame(HALF_COLS, HALF_COLS)
            if game2: game2.update()

            mat = [[COLOR_BLACK]*(COLS+2) for _ in range(ROWS+2)]
            game1.render(mat)
            if game2: game2.render(mat)

            # собираем изменённые пиксели
            changed = [(c, ROWS-r+1, mat[r][c]) 
                       for r in range(1, ROWS+1) 
                       for c in range(1, COLS+1) 
                       if mat[r][c]!=mat_prev[r][c]]
            mat_prev = mat

            if changed:
                cmds = build_command_from_pixels(changed)
                await send_commands(client_ble, cmds)

        # в режиме Control MQTT‑команда уже ушла сразу в handler

        await asyncio.sleep(1/FPS)

# ---------------- Entrypoint ----------------

async def run():
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, signal_handler)
    loop.add_signal_handler(signal.SIGINT, signal_handler)

    async with BleakClient(DEVICE_ADDRESS) as client_ble:
        await client_ble.get_services()
        print("BLE connected")
        await enter_per_led_mode(client_ble)

        # запускаем параллельно MQTT и игровой цикл
        await asyncio.gather(
            mqtt_handler(client_ble),
            game_loop(client_ble),
        )

if __name__ == "__main__":
    asyncio.run(run())
