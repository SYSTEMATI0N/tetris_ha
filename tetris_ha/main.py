import asyncio
import random
from bleak import BleakClient
from aiohttp import web

# Константы
COLOR_BLACK = (0, 0, 0)
COLOR_PALETTE = [
    (0, 255, 255),  # Cyan
    (255, 255, 0),  # Yellow
    (128, 0, 128),  # Purple
    (255, 165, 0),  # Orange
    (0, 0, 255),    # Blue
    (0, 255, 0),    # Green
    (255, 0, 0),    # Red
]
ROWS, COLS = 20, 20
HALF_COLS = COLS // 2
FPS = 4
TARGET_HEIGHT = ROWS / 2
ALPHA = 1.0  # weight for height deviation
BETA = 5.0   # weight for holes
GAMMA = 2.0  # weight for height variance
HELP_THRESHOLD = 16

DEVICE_ADDRESS = "BE:16:FA:00:03:7A"
CHAR_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"


CMD_MAP = {
    "Вкл": bytearray.fromhex("7e0704ff00010201ef"),
    "Выкл": bytearray.fromhex("7e07040000000201ef"),
    "Синий": bytearray.fromhex("7e0705030000ff10ef"),
    "Бирюзовый": bytearray.fromhex("7e07050300ffff10ef"),
    "Зеленый": bytearray.fromhex("7e07050300ff0010ef"),
    "Красный": bytearray.fromhex("7e070503ff000010ef"),
    "Фиолетовый": bytearray.fromhex("7e070503ff00ff10ef"),
    "Белый": bytearray.fromhex("7e070503ffffff10ef"),
    "Жёлтый": bytearray.fromhex("7e070503ffff0010ef"),
    "Розовый": bytearray.fromhex("7e070503ff008010ef"),
}
client = None 

async def ble_connect():
    global client
    if client is None or not client.is_connected:
        if client is not None:
            await client.disconnect()
        client = BleakClient(DEVICE_ADDRESS)
        await client.connect()
        await client.get_services()


async def handle_mode(request):
    global game_task  # 
    cmd = request.query.get("cmd")
    if cmd in CMD_MAP:
        try:
            await send_control_command(CMD_MAP[cmd])
            return web.Response(text=f"Команда {cmd} отправлена")
        except Exception as e:
            return web.Response(status=500, text=f"Ошибка BLE: {e}")
    return web.Response(status=400, text="Неверная команда")



stop_event = asyncio.Event()




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
    try:
        if not client.is_connected:
            await client.connect()
            await client.get_services()
        for cmd in commands:
            print(f"📦 Отправка BLE пакета: {cmd.hex()}")
            await client.write_gatt_char(CHAR_UUID, cmd, response=False)
    except Exception as e:
        print(f"Ошибка при отправке BLE пакетов: {e}, пытаюсь переподключиться...")
        try:
            await client.disconnect()
        except Exception:
            pass
        await asyncio.sleep(1)
        await client.connect()
        await client.get_services()
        for cmd in commands:
            await client.write_gatt_char(CHAR_UUID, cmd, response=False)


async def send_control_command(client, cmd):
    try:
        if not client.is_connected:
            await client.connect()
            await client.get_services()
        await client.write_gatt_char(CHAR_UUID, cmd, response=False)
    except Exception as e:
        print(f"Ошибка при отправке BLE команды: {e}, пытаюсь переподключиться...")
        try:
            await client.disconnect()
        except Exception:
            pass
        await asyncio.sleep(1)
        await client.connect()
        await client.get_services()
        await client.write_gatt_char(CHAR_UUID, cmd, response=False)


async def enter_per_led_mode(client):
    for cmd in INIT_CMDS:
        await send_commands(client, [cmd])
        await asyncio.sleep(0.05)

# --- TetrisGame класс 
TETROMINOS = {
    'I': [(0, 0), (1, 0), (2, 0), (3, 0)],
    'O': [(0, 0), (0, 1), (1, 0), (1, 1)],
    'T': [(0, 1), (1, 0), (1, 1), (1, 2)],
    'L': [(0, 0), (1, 0), (2, 0), (2, 1)],
    'J': [(0, 1), (1, 1), (2, 1), (2, 0)],
    'S': [(0, 1), (0, 2), (1, 0), (1, 1)],
    'Z': [(0, 0), (0, 1), (1, 1), (1, 2)],
}


class TetrisGame:
    def __init__(self, cols_start, cols_count):
        self.cols_start = cols_start
        self.cols_count = cols_count
        self.field = [[False] * cols_count for _ in range(ROWS)]
        self.color_field = [[COLOR_BLACK for _ in range(cols_count)] for _ in range(ROWS)]
        self.current_piece = None
        self.piece_row = -2
        self.piece_col = cols_count // 2 - 1
        self.piece_blocks = []
        self.piece_color = COLOR_PALETTE[0]
        self.game_over = False
        self.locked_pieces_count = 0
        # Для AI‑логики
        self.target_col = None
        self.target_blocks = None
        self.spawn_new_piece()

    def spawn_new_piece(self):
        self.current_piece = random.choice(list(TETROMINOS.keys()))
        self.piece_blocks = TETROMINOS[self.current_piece]
        self.piece_row = -2
        self.piece_col = self.cols_count // 2 - 2
        self.piece_color = random.choice(COLOR_PALETTE)
        # сброс цели
        self.target_blocks = None
        self.target_col = None
        # проверка Game Over
        for r, c in self.piece_blocks:
            nr, nc = self.piece_row + r, self.piece_col + c
            if 0 <= nr < ROWS and self.field[nr][nc]:
                self.game_over = True
                self.reset_game()
                break

    def reset_game(self):
        self.field = [[False] * self.cols_count for _ in range(ROWS)]
        self.color_field = [[COLOR_BLACK for _ in range(self.cols_count)] for _ in range(ROWS)]
        self.game_over = False
        self.locked_pieces_count = 0
        self.spawn_new_piece()

    def can_move(self, dr, dc):
        for r, c in self.piece_blocks:
            nr, nc = self.piece_row + r + dr, self.piece_col + c + dc
            if nr >= ROWS or nc < 0 or nc >= self.cols_count or nr < -2:
                return False
            if nr >= 0 and self.field[nr][nc]:
                return False
        return True

    def lock_piece(self):
        # сброс цели
        self.target_blocks = None
        self.target_col = None
        for r, c in self.piece_blocks:
            nr, nc = self.piece_row + r, self.piece_col + c
            if 0 <= nr < ROWS and 0 <= nc < self.cols_count:
                self.field[nr][nc] = True
                self.color_field[nr][nc] = self.piece_color
        self.locked_pieces_count += 1
        self.clear_lines()
        self.spawn_new_piece()

    def clear_lines(self):
        new_field, new_color_field = [], []
        for row_idx in range(ROWS):
            if not all(self.field[row_idx]):
                new_field.append(self.field[row_idx])
                new_color_field.append(self.color_field[row_idx])
        for _ in range(ROWS - len(new_field)):
            new_field.insert(0, [False] * self.cols_count)
            new_color_field.insert(0, [COLOR_BLACK] * self.cols_count)
        self.field, self.color_field = new_field, new_color_field

    def rotate_piece(self):
        if self.current_piece == 'O':
            return
        new_blocks = [(-c, r) for r, c in self.piece_blocks]
        for r, c in new_blocks:
            nr, nc = self.piece_row + r, self.piece_col + c
            if nr < -2 or nr >= ROWS or nc < 0 or nc >= self.cols_count or (nr >= 0 and self.field[nr][nc]):
                return
        self.piece_blocks = new_blocks

    def get_rotations(self, blocks):
        seen, rots = set(), []
        curr = list(blocks)
        for _ in range(4):
            norm = tuple(sorted(curr))
            if norm in seen:
                break
            seen.add(norm)
            rots.append(list(curr))
            curr = [(-c, r) for r, c in curr]
        return rots

    def simulate(self, blocks, col):
        temp = [row[:] for row in self.field]
        row = -2
        while self.can_move(blocks, row + 1, col):
            row += 1
        for r, c in blocks:
            nr, nc = row + r, col + c
            if 0 <= nr < ROWS:
                temp[nr][nc] = True
        heights, holes = [], 0
        for cc in range(self.cols_count):
            seen_block, h = False, 0
            for rr in range(ROWS):
                if temp[rr][cc]:
                    if not seen_block:
                        h, seen_block = ROWS - rr, True
                elif seen_block:
                    holes += 1
            heights.append(h)
        return sum(heights) / self.cols_count, holes, heights

    def update(self):
        if self.game_over:
            return

        # 1) Подбор цели
        if self.target_blocks is None:
            best_score, best = float('inf'), None
            for base in TETROMINOS.values():
                for blocks in self.get_rotations(base):
                    minc, maxc = min(c for _, c in blocks), max(c for _, c in blocks)
                    for col in range(-minc, self.cols_count - maxc):
                        if not self.can_move(blocks, self.piece_row, col):
                            continue
                        avg_h, holes, heights = self.simulate(blocks, col)
                        var = max(heights) - min(heights)
                        score = ALPHA * abs(avg_h - TARGET_HEIGHT) + BETA * holes + GAMMA * var
                        if score < best_score:
                            best_score, best = score, (blocks, col)
            if best:
                self.target_blocks, self.target_col = best

        # 2) Гориз. движение
        if self.target_col is not None:
            if self.piece_col < self.target_col and self.can_move(0, 1):
                self.piece_col += 1
            elif self.piece_col > self.target_col and self.can_move(0, -1):
                self.piece_col -= 1

        # 3) Поворот
        if self.target_blocks is not None and self.piece_blocks != self.target_blocks:
            rots = self.get_rotations(self.piece_blocks)
            if self.target_blocks in rots:
                idx = rots.index(self.piece_blocks)
                candidate = rots[(idx + 1) % len(rots)]
                if self.can_move(candidate, 0, 0):
                    self.piece_blocks = candidate

        # 4) Падение
        if self.can_move(1, 0):
            self.piece_row += 1
        else:
            self.lock_piece()

    def render(self, led_matrix):
        for r in range(ROWS):
            for c in range(self.cols_count):
                led_matrix[r+1][c+self.cols_start+1] = self.color_field[r][c] if self.field[r][c] else COLOR_BLACK
        for r, c in self.piece_blocks:
            nr, nc = self.piece_row+r+1, self.piece_col+c+self.cols_start+1
            if 0 <= nr < ROWS+2 and 0 <= nc < COLS+2:
                led_matrix[nr][nc] = self.piece_color

# -----------------------

# Game loop и управление задачей игры
game_task = None

async def game_loop(client):
    game1 = TetrisGame(0, HALF_COLS)
    game2 = None
    led_matrix = [[COLOR_BLACK for _ in range(COLS+2)] for _ in range(ROWS+2)]
    prev_matrix = [[COLOR_BLACK for _ in range(COLS+2)] for _ in range(ROWS+2)]

    try:
        while not stop_event.is_set():
            game1.update()
            if game2 is None and game1.locked_pieces_count >= 10:
                print("🚀 Запуск второй игры после 10 упавших фигур!")
                game2 = TetrisGame(HALF_COLS, HALF_COLS)
            if game2:
                game2.update()
            for r in range(ROWS+2):
                for c in range(COLS+2):
                    led_matrix[r][c] = COLOR_BLACK
            game1.render(led_matrix)
            if game2:
                game2.render(led_matrix)
            changed = []
            for r in range(1, ROWS+1):
                for c in range(1, COLS+1):
                    if led_matrix[r][c] != prev_matrix[r][c]:
                        rotated_row = c
                        rotated_col = ROWS - r + 1
                        changed.append((rotated_row, rotated_col, led_matrix[r][c]))
            prev_matrix = [row[:] for row in led_matrix]
            if changed:
                commands = build_command_from_pixels(changed)
                await send_commands(client, commands)
            await asyncio.sleep(1 / FPS)
    except asyncio.CancelledError:
        print("Игра остановлена")
# -----------------------


# Обработчик HTTP-запроса
async def handle_mode(request):
    global game_task
    cmd = request.rel_url.query.get("cmd")
    if cmd is None:
        return web.Response(text="Параметр cmd обязателен", status=400)
    cmd = cmd.strip()
    print(f"HTTP: получена команда: {cmd}")

    client = request.app['ble_client']

    # Обработка команды
    if cmd == "Тетрис":
     if game_task is None or game_task.done():
        if not client.is_connected:
            await client.connect()
            await client.get_services()
        print("⏳ Переход в режим индивидуального управления диодами...")
        await enter_per_led_mode(client)
        game_task = asyncio.create_task(game_loop(client))
        return web.Response(text="Игра Тетрис запущена")
     else:
        return web.Response(text="Игра уже запущена")
    elif cmd == "Стоп":
        if game_task and not game_task.done():
            game_task.cancel()
            try:
                await game_task
            except asyncio.CancelledError:
                pass
            game_task = None
            return web.Response(text="Игра остановлена")
        else:
            return web.Response(text="Игра не запущена")
    elif cmd in CMD_MAP:
        print("⏳ Переход в режим глобального управления диодами...")
        if game_task and not game_task.done():
            game_task.cancel()
            try:
                await game_task
            except asyncio.CancelledError:
                pass
            game_task = None
        await send_control_command(client, CMD_MAP[cmd])
        return web.Response(text=f"Команда {cmd} отправлена")
    else:
        return web.Response(text=f"Неизвестная команда: {cmd}", status=400)

async def start_app(client):
    app = web.Application()
    app['ble_client'] = client

    async def on_shutdown(app):
        if client.is_connected:
            await client.disconnect()

    app.on_shutdown.append(on_shutdown)
    
    app.add_routes([web.get('/mode', handle_mode)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🚀 HTTP сервер запущен на http://0.0.0.0:8080")

async def main():
    async with BleakClient(DEVICE_ADDRESS) as client:
        if not client.is_connected:
            print("❌ Не удалось подключиться к BLE устройству.")
            return
        print("✅ Подключено к BLE.")
        await enter_per_led_mode(client)
        await start_app(client)
        await asyncio.Event().wait()  # Ждем вечности, пока не убьют процесс

if __name__ == '__main__':
    asyncio.run(main())
