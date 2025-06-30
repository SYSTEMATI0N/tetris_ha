import asyncio
from aiohttp import web
from bleak import BleakClient
import random
import copy

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
    def __init__(self, cols_start, cols_count):
        self.cols_start = cols_start
        self.cols_count = cols_count
        self.field = [[False] * cols_count for _ in range(ROWS)]
        self.color_field = [[COLOR_BLACK for _ in range(cols_count)] for _ in range(ROWS)]
        self.spawn_new_piece()

    def spawn_new_piece(self):
        self.current_piece = random.choice(list(TETROMINOS.keys()))
        self.piece_blocks = copy.deepcopy(TETROMINOS[self.current_piece])
        self.piece_row = -2
        self.piece_col = self.cols_count // 2 - 2
        self.piece_color = random.choice(COLOR_PALETTE)
        self.game_over = self._check_spawn_collision()
        self.locked_pieces_count = getattr(self, 'locked_pieces_count', 0)

    def _check_spawn_collision(self):
        for r, c in self.piece_blocks:
            nr, nc = self.piece_row + r, self.piece_col + c
            if 0 <= nr < ROWS and self.field[nr][nc]:
                return True
        return False

    def reset_game(self):
        self.field = [[False] * self.cols_count for _ in range(ROWS)]
        self.color_field = [[COLOR_BLACK for _ in range(self.cols_count)] for _ in range(ROWS)]
        self.locked_pieces_count = 0
        self.spawn_new_piece()
        self.game_over = False

    def can_place(self, blocks, row, col, field=None):
        fld = field or self.field
        for r, c in blocks:
            nr, nc = row + r, col + c
            if nr >= ROWS or nc < 0 or nc >= self.cols_count or nr < 0:
                return False
            if fld[nr][nc]:
                return False
        return True

    def place(self, blocks, row, col, field, color_field=None, color=None):
        cf = color_field or self.color_field
        for r, c in blocks:
            nr, nc = row + r, col + c
            if 0 <= nr < ROWS:
                field[nr][nc] = True
                if color is not None:
                    cf[nr][nc] = color

    def clear_lines(self):
        new_f, new_cf = [], []
        for r in range(ROWS):
            if all(self.field[r]):
                continue
            new_f.append(self.field[r])
            new_cf.append(self.color_field[r])
        lines_cleared = ROWS - len(new_f)
        for _ in range(lines_cleared):
            new_f.insert(0, [False] * self.cols_count)
            new_cf.insert(0, [COLOR_BLACK] * self.cols_count)
        self.field, self.color_field = new_f, new_cf
        return lines_cleared

    def get_rotations(self, blocks):
        rotations = []
        current = blocks
        for _ in range(4):
            # Поворачиваем
            current = [(-c, r) for r, c in current]
            # Нормализуем положение (минимум 0)
            min_r = min(r for r, c in current)
            min_c = min(c for r, c in current)
            norm = sorted([(r - min_r, c - min_c) for r, c in current])
            if norm not in rotations:
                rotations.append(norm)
        return rotations

    def count_holes(self, field):
        holes = 0
        for c in range(self.cols_count):
            block_found = False
            for r in range(ROWS):
                if field[r][c]:
                    block_found = True
                elif block_found and not field[r][c]:
                    holes += 1
        return holes

    def column_heights(self, field):
        heights = []
        for c in range(self.cols_count):
            h = 0
            for r in range(ROWS):
                if field[r][c]:
                    h = ROWS - r
                    break
            heights.append(h)
        return heights

    def evaluate(self, field):
        heights = self.column_heights(field)
        max_height = max(heights)
        holes = self.count_holes(field)
        center = self.cols_count // 2
        # Оценка удаление от центра - среднее отклонение
        dev = sum(abs(c - center) for c in range(self.cols_count) if heights[c] > 0)
        score = -max_height * 10 - holes * 5 - dev * 1
        return score

    def find_best_move(self):
        best_score = -float('inf')
        best_rot, best_col = None, None
        rotations = self.get_rotations(self.piece_blocks)
        for rot in rotations:
            w = max(c for _, c in rot) + 1
            for col in range(self.cols_count - w + 1):
                # Найти, куда упадет
                row = -max(r for r, _ in rot)
                while self.can_place(rot, row + 1, col):
                    row += 1
                # Моделируем поле
                temp_field = copy.deepcopy(self.field)
                self.place(rot, row, col, temp_field)
                score = self.evaluate(temp_field)
                if score > best_score:
                    best_score = score
                    best_rot, best_col = rot, col
        return best_rot, best_col

    def update(self):
        if self.game_over:
            return
        # Находим лучший ход
        rot, col = self.find_best_move()
        # Применяем поворот
        self.piece_blocks = rot
        self.piece_col = col
        # Опускаем донизу
        while self.can_place(self.piece_blocks, self.piece_row + 1, self.piece_col):
            self.piece_row += 1
        # Блокируем
        self.lock_piece()
        left_fill = self.column_fill(self.piece_col - 1) if self.piece_col > 0 else 1000
        right_fill = self.column_fill(self.piece_col + max(c for _, c in self.piece_blocks) + 1) if (self.piece_col + max(c for _, c in self.piece_blocks) + 1) < self.cols_count else 1000

        if left_fill < right_fill and self.can_move(0, -1):
            self.piece_col -= 1
        elif right_fill < left_fill and self.can_move(0, 1):
            self.piece_col += 1

        if random.random() < 0.3:
            old_blocks = self.piece_blocks[:]
            self.rotate_piece()
            if not self.can_move(0, 0):
                self.piece_blocks = old_blocks

        if self.can_move(1, 0):
            self.piece_row += 1
        else:
            self.lock_piece()

    def column_fill(self, col):
        if col < 0 or col >= self.cols_count:
            return 1000
        return sum(1 for r in range(ROWS) if self.field[r][col])

    def render(self, led_matrix):
        for r in range(ROWS):
            for c in range(self.cols_count):
                color = self.color_field[r][c] if self.field[r][c] else COLOR_BLACK
                led_matrix[r+1][c + self.cols_start + 1] = color

        for r, c in self.piece_blocks:
            nr = self.piece_row + r + 1
            nc = self.piece_col + c + self.cols_start + 1
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
