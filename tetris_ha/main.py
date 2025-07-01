import asyncio
from aiohttp import web
from bleak import BleakClient
import random
import copy
import signal

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

ROWS, COLS = 20, 20
HALF_COLS = COLS // 2
FPS = 4
TARGET_HEIGHT = ROWS / 2
ALPHA, BETA, GAMMA = 1.0, 5.0, 2.0
HELP_THRESHOLD = 16
game_tasks: list[asyncio.Task] = []
stop_event = asyncio.Event()

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
    def __init__(self, cols_start, cols_count, seed=None):
        self.cols_start = cols_start
        self.cols_count = cols_count

        import time
        if seed is None:
            base = cols_start + int(time.time() * 1000)
        else:
            base = seed
        self.rng = random.Random(base)

        self.field = [[False] * cols_count for _ in range(ROWS)]
        self.color_field = [[COLOR_BLACK for _ in range(cols_count)] for _ in range(ROWS)]
        self.piece_blocks = []
        self.piece_row = -2
        self.piece_col = cols_count // 2 - 1
        self.piece_color = COLOR_PALETTE[0]
        self.game_over = False
        self.locked_pieces_count = 0
        self.target_blocks = None
        self.target_col = None
        self.spawn_new_piece()

    def can_place(self, blocks, row, col):
        for r, c in blocks:
            nr, nc = row + r, col + c
            if nc < 0 or nc >= self.cols_count or nr >= ROWS:
                return False
            if nr >= 0 and self.field[nr][nc]:
                return False
        return True

    def get_rotations(self, blocks):
        seen = set()
        rotations = []
        current = list(blocks)
        for _ in range(4):
            norm = tuple(sorted(current))
            if norm in seen:
                break
            seen.add(norm)
            rotations.append(list(current))
            current = [(-c, r) for r, c in current]
        return rotations

    def simulate(self, blocks, col):
        temp = [row[:] for row in self.field]
        row = -2
        while self.can_place(blocks, row + 1, col):
            row += 1
        for r, c in blocks:
            nr, nc = row + r, col + c
            if 0 <= nr < ROWS:
                temp[nr][nc] = True
        heights, holes = [], 0
        for c in range(self.cols_count):
            seen = False
            h = 0
            for r in range(ROWS):
                if temp[r][c]:
                    if not seen:
                        h = ROWS - r
                        seen = True
                elif seen:
                    holes += 1
            heights.append(h)
        avg_h = sum(heights) / self.cols_count
        return avg_h, holes, heights

    def max_height(self):
        m = 0
        for c in range(self.cols_count):
            for r in range(ROWS):
                if self.field[r][c]:
                    m = max(m, ROWS - r)
                    break
        return m

    def spawn_new_piece(self):
        start_col = self.cols_count // 2 - 1
        if self.max_height() >= HELP_THRESHOLD:
            # Use AI to find the best piece and position
            best_score, best = float('inf'), None
            for shape in TETROMINOS.values():
                for blocks in self.get_rotations(shape):
                    minc, maxc = min(c for _, c in blocks), max(c for _, c in blocks)
                    for col in range(-minc, self.cols_count - maxc):
                        if not self.can_place(blocks, -2, col):
                            continue
                        avg_h, holes, heights = self.simulate(blocks, col)
                        variance = max(heights) - min(heights)
                        score = ALPHA * abs(avg_h - TARGET_HEIGHT) + BETA * holes + GAMMA * variance
                        if score < best_score:
                            best_score, best = score, (blocks, col)
            if best:
                self.piece_blocks, self.piece_col = best
            else:
                self.game_over = True
                return
        else:
            # Randomly select a piece
            choice = self.rng.choice(list(TETROMINOS.keys()))
            blocks0 = TETROMINOS[choice]
            if self.can_place(blocks0, -2, start_col):
                self.piece_blocks = blocks0
                self.piece_col = start_col
            else:
                self.spawn_new_piece()  # Recursive call to try another piece
                return

        self.piece_row = -2
        self.piece_color = self.rng.choice(COLOR_PALETTE)
        self.target_blocks = None
        self.target_col = None
        if not self.can_place(self.piece_blocks, self.piece_row, self.piece_col):
            self.game_over = True

    def update(self):
        if self.game_over:
            return
        # Determine target
        if self.target_blocks is None:
            best_score, best = float('inf'), None
            for blocks in self.get_rotations(self.piece_blocks):
                minc, maxc = min(c for _, c in blocks), max(c for _, c in blocks)
                for col in range(-minc, self.cols_count - maxc):
                    if not self.can_place(blocks, self.piece_row, col):
                        continue
                    avg_h, holes, heights = self.simulate(blocks, col)
                    variance = max(heights) - min(heights)
                    score = ALPHA * abs(avg_h - TARGET_HEIGHT) + BETA * holes + GAMMA * variance
                    if score < best_score:
                        best_score, best = score, (blocks, col)
            self.target_blocks, self.target_col = best if best else (self.piece_blocks, self.piece_col)
        # Move towards target
        if self.piece_col < self.target_col and self.can_place(self.piece_blocks, self.piece_row, self.piece_col + 1):
            self.piece_col += 1
        elif self.piece_col > self.target_col and self.can_place(self.piece_blocks, self.piece_row, self.piece_col - 1):
            self.piece_col -= 1
        # Rotate if possible, only when piece_row >= 3
        if self.piece_blocks != self.target_blocks and self.piece_row >= 3:
            rots = self.get_rotations(self.piece_blocks)
            if self.target_blocks in rots:
                next_block = rots[(rots.index(self.piece_blocks) + 1) % len(rots)]
                if self.can_place(next_block, self.piece_row, self.piece_col):
                    self.piece_blocks = next_block
                    return
        # Fall or lock
        if self.can_place(self.piece_blocks, self.piece_row + 1, self.piece_col):
            self.piece_row += 1
        else:
            self.lock_piece()

    def lock_piece(self):
        for r, c in self.piece_blocks:
            nr, nc = self.piece_row + r, self.piece_col + c
            if 0 <= nr < ROWS:
                self.field[nr][nc] = True
                self.color_field[nr][nc] = self.piece_color
        self.locked_pieces_count += 1
        # Clear lines
        new_f, new_c, cleared = [], [], 0
        for r in range(ROWS):
            if all(self.field[r]):
                cleared += 1
            else:
                new_f.append(self.field[r])
                new_c.append(self.color_field[r])
        for _ in range(cleared):
            new_f.insert(0, [False] * self.cols_count)
            new_c.insert(0, [COLOR_BLACK] * self.cols_count)
        self.field, self.color_field = new_f, new_c
        self.spawn_new_piece()

    def render(self, led_matrix):
        # Draw field
        for r in range(ROWS):
            for c in range(self.cols_count):
                led_matrix[r + 1][c + self.cols_start + 1] = self.color_field[r][c] if self.field[r][c] else COLOR_BLACK
        # Draw active piece
        for r, c in self.piece_blocks:
            nr, nc = self.piece_row + r + 1, self.piece_col + c + self.cols_start + 1
            if 0 <= nr < ROWS + 2 and 0 <= nc < COLS + 2:
                led_matrix[nr][nc] = self.piece_color
# -----------------------
async def single_game_loop(client, cols_start, cols_count, seed=None):
    """
    Один цикл игры Тетрис на диапазоне колонок [cols_start, cols_start+cols_count).
    Рендерит и отправляет только своё поле.
    """
    game = TetrisGame(cols_start, cols_count, seed=seed)
    # матрица с границами: +2 по строкам и столбцам
    led_matrix = [[COLOR_BLACK]*(COLS+2) for _ in range(ROWS+2)]
    prev_matrix = [row[:] for row in led_matrix]

    try:
        while True:
            game.update()

            # очистка матрицы перед рендером
            for r in range(ROWS+2):
                for c in range(COLS+2):
                    led_matrix[r][c] = COLOR_BLACK

            # отрисовка только своего игрового поля
            game.render(led_matrix)

            # собираем отличия от prev_matrix
            changed = []
            for r in range(1, ROWS+1):
                for c in range(1, COLS+1):
                    if led_matrix[r][c] != prev_matrix[r][c]:
                        # поворот координат под вашу штору
                        rotated_row = c
                        rotated_col = ROWS - r + 1
                        changed.append((rotated_row, rotated_col, led_matrix[r][c]))
            prev_matrix = [row[:] for row in led_matrix]

            # отправляем пакеты, если что-то изменилось
            if changed:
                cmds = build_command_from_pixels(changed)
                await send_commands(client, cmds)

            await asyncio.sleep(1 / FPS)

    except asyncio.CancelledError:
        # при отмене просто выходим из функции
        return


# -----------------------


# Обработчик HTTP-запроса
async def handle_mode(request):
    """
    HTTP API:
      /mode?cmd=Тетрис — запускает две параллельные игры Тетрис (левая и правая половины)
      /mode?cmd=Стоп    — останавливает все запущенные игры
      /mode?cmd=<цвет>  — глобально отправляет BLE‑команду (после остановки игр)
    """
    cmd = request.rel_url.query.get("cmd")
    if cmd is None:
        return web.Response(text="Параметр cmd обязателен", status=400)
    cmd = cmd.strip()
    print(f"HTTP: получена команда: {cmd}")

    client = request.app['ble_client']

    # --- 1) Запуск игр Тетрис ---
    if cmd == "Тетрис":
        # если уже есть активные таски — отказываем
        if any(not t.done() for t in game_tasks):
            return web.Response(text="Игра уже запущена")

        # готовим LED‑штору
        if not client.is_connected:
            await client.connect()
            await client.get_services()
        await enter_per_led_mode(client)

        # создаём две параллельные игры: левая и правая половины
        task1 = asyncio.create_task(single_game_loop(client, 0, HALF_COLS, seed=1))
        task2 = asyncio.create_task(single_game_loop(client, HALF_COLS, HALF_COLS, seed=2))
        game_tasks.clear()
        game_tasks.extend([task1, task2])

        return web.Response(text="Две игры Тетрис запущены")

    # --- 2) Остановка всех игр ---
    elif cmd == "Стоп":
        if not any(not t.done() for t in game_tasks):
            return web.Response(text="Игра не запущена")

        # отменяем и ждём завершения
        for t in game_tasks:
            t.cancel()
        await asyncio.gather(*game_tasks, return_exceptions=True)
        game_tasks.clear()

        return web.Response(text="Все игры остановлены")

    # --- 3) Глобальные цветовые команды ---
    elif cmd in CMD_MAP:
        # сначала убираем любые играющие таски
        if any(not t.done() for t in game_tasks):
            for t in game_tasks:
                t.cancel()
            await asyncio.gather(*game_tasks, return_exceptions=True)
            game_tasks.clear()

        # шлём команду на всю штору
        if not client.is_connected:
            await client.connect()
            await client.get_services()
        await send_control_command(client, CMD_MAP[cmd])

        return web.Response(text=f"Команда {cmd} отправлена")

    # --- 4) Неизвестный запрос ---
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

async def shutdown(loop, client):
    # отменяем все таски игр
    for t in game_tasks:
        t.cancel()
    # ждём их завершения
    await asyncio.gather(*game_tasks, return_exceptions=True)
    # чисто отключаем BLE
    if client.is_connected:
        await client.disconnect()
    loop.stop()

async def main():
    loop = asyncio.get_running_loop()
    # ловим SIGTERM
   # loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown(loop, client)))

    async with BleakClient(DEVICE_ADDRESS) as client:
        if not client.is_connected:
            print("❌ Не удалось подключиться к BLE.")
            return
        print("✅ Подключено к BLE.")
        await start_app(client)
        await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
