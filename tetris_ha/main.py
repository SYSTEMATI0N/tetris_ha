import asyncio
import random
from bleak import BleakClient

DEVICE_ADDRESS = "BE:16:FA:00:03:7A"
CHAR_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

ROWS, COLS = 20, 20  # Общее поле
HALF_COLS = COLS // 2  # 10

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
        # ... rest of the class ...
        pass

async def run():
    async with BleakClient(DEVICE_ADDRESS) as client:
        if not client.is_connected:
            print("❌ Не удалось подключиться.")
            return
        print("✅ Подключено.")
        await enter_per_led_mode(client)
        # Placeholder for game loop

if __name__ == '__main__':
    asyncio.run(run())
