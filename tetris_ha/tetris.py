import asyncio
import random
from bleak import BleakClient

DEVICE_ADDRESS = "BE:16:FA:00:03:7A"
CHAR_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

ROWS, COLS = 20, 20
HALF_COLS = COLS // 2
FPS = 4

COLOR_PALETTE = [
    (20, 0, 80),
    (56, 0, 145),
    (57, 0, 98),
    (108, 0, 142),
    (180, 0, 82),
    (95, 24, 13),
]

COLOR_BLACK = (0, 0, 0)

INIT_CMDS = [
    bytearray.fromhex("7e075100ffffff00ef"),
    bytearray.fromhex("7e07580000ffff00ef"),
    bytearray.fromhex("7e07640101e00000" + "ff" * 70 + "ef"),
]

def rgb_to_hex_str(rgb):
    return ''.join(f"{c:02x}" for c in rgb)

def build_command_from_pixels(pixels):
    commands = []
    i = 0
    while i < len(pixels):
        chunk = pixels[i:i+10]
        body = ""
        for row, col, color in chunk:
            body += f"{row:02x}{col:02x}{rgb_to_hex_str(color)}"
        for _ in range(10 - len(chunk)):
            body += "ffffffffff"
        cmd = bytearray.fromhex("7e0764" + body + "ef")
        commands.append(cmd)
        i += 10
    return commands

async def send_commands(client, commands):
    mtu = getattr(client, 'mtu_size', 23)
    max_payload = mtu - 3
    for cmd in commands:
        for i in range(0, len(cmd), max_payload):
            chunk = cmd[i:i+max_payload]
            print(f"📦 Отправка BLE пакета: {chunk.hex()}")
            await client.write_gatt_char(CHAR_UUID, chunk, response=False)

async def enter_per_led_mode(client):
    for cmd in INIT_CMDS:
        await send_commands(client, [cmd])
        await asyncio.sleep(0.05)

class TetrisGame:
    def __init__(self, cols_start, cols_count):
        self.cols_start = cols_start
        self.cols_count = cols_count
        self.field = [[False]*cols_count for _ in range(ROWS)]
        self.color_field = [[COLOR_BLACK for _ in range(cols_count)] for _ in range(ROWS)]
        self.current_piece = None
        self.piece_row = -2
        self.piece_col = cols_count // 2 - 1
        self.piece_blocks = []
        self.piece_color = COLOR_PALETTE[0]
        self.game_over = False
        self.locked_pieces_count = 0
        self.spawn_new_piece()

    # Methods spawn_new_piece, reset_game, can_move, lock_piece,
    # clear_lines, rotate_piece, update, column_fill, render same as above...

async def run():
    async with BleakClient(DEVICE_ADDRESS) as client:
        if not client.is_connected:
            print("❌ Не удалось подключиться.")
            return
        print("✅ Подключено.")
        await enter_per_led_mode(client)
        # Simplified run: just a placeholder for full game loop
        # await game_loop(client)

if __name__ == '__main__':
    asyncio.run(run())
