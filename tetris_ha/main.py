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
    bytearray.fromhex("7e0704ff00010201ef"),
    bytearray.fromhex("7e075100ffffff00ef"),
    bytearray.fromhex("7e07580000ffff00ef"),
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

TETROMINOS = {
    'I': [(0,0), (1,0), (2,0), (3,0)],
    'O': [(0,0), (0,1), (1,0), (1,1)],
    'T': [(0,1), (1,0), (1,1), (1,2)],
    'S': [(0,1), (0,2), (1,0), (1,1)],
    'Z': [(0,0), (0,1), (1,1), (1,2)],
    'J': [(0,0), (1,0), (2,0), (2,1)],
    'L': [(0,1), (1,1), (2,0), (2,1)],
}

class TetrisGame:
    def __init__(self, cols_start, cols_count):
        self.cols_start = cols_start  # Начало по горизонтали (0 или 10)
        self.cols_count = cols_count  # Ширина поля (10)
        self.field = [[False]*cols_count for _ in range(ROWS)]
        self.color_field = [[COLOR_BLACK for _ in range(cols_count)] for _ in range(ROWS)]
        self.current_piece = None
        self.piece_row = -2
        self.piece_col = cols_count // 2 - 1
        self.piece_blocks = []
        self.piece_color = COLOR_PALETTE[0]
        self.game_over = False
        self.locked_pieces_count = 0  # счётчик упавших фигур
        self.spawn_new_piece()

    def spawn_new_piece(self):
        self.current_piece = random.choice(list(TETROMINOS.keys()))
        self.piece_blocks = TETROMINOS[self.current_piece]
        self.piece_row = -2
        self.piece_col = self.cols_count // 2 - 2
        self.piece_color = random.choice(COLOR_PALETTE)

        for r, c in self.piece_blocks:
            nr = self.piece_row + r
            nc = self.piece_col + c
            if 0 <= nr < ROWS and self.field[nr][nc]:
                self.game_over = True
                print(f"💀 Game Over на поле начиная с колонки {self.cols_start}! Перезапуск...")
                self.reset_game()
                break

    def reset_game(self):
        self.field = [[False]*self.cols_count for _ in range(ROWS)]
        self.color_field = [[COLOR_BLACK for _ in range(self.cols_count)] for _ in range(ROWS)]
        self.game_over = False
        self.locked_pieces_count = 0
        self.spawn_new_piece()

    def can_move(self, dr, dc):
        for r, c in self.piece_blocks:
            nr = self.piece_row + r + dr
            nc = self.piece_col + c + dc
            if nr >= ROWS or nc < 0 or nc >= self.cols_count:
                return False
            if nr >= 0 and self.field[nr][nc]:
                return False
            if nr < -2:
                return False
        return True

    def lock_piece(self):
        for r, c in self.piece_blocks:
            nr = self.piece_row + r
            nc = self.piece_col + c
            if 0 <= nr < ROWS and 0 <= nc < self.cols_count:
                self.field[nr][nc] = True
                self.color_field[nr][nc] = self.piece_color
        self.locked_pieces_count += 1
        self.clear_lines()
        self.spawn_new_piece()

    def clear_lines(self):
        new_field = []
        new_color_field = []
        lines_cleared = 0
        for row_idx in range(ROWS):
            if all(self.field[row_idx]):
                lines_cleared += 1
            else:
                new_field.append(self.field[row_idx])
                new_color_field.append(self.color_field[row_idx])
        for _ in range(lines_cleared):
            new_field.insert(0, [False]*self.cols_count)
            new_color_field.insert(0, [COLOR_BLACK]*self.cols_count)
        self.field = new_field
        self.color_field = new_color_field

    def rotate_piece(self):
        if self.current_piece == 'O':
            return
        new_blocks = [(-c, r) for r, c in self.piece_blocks]
        for r, c in new_blocks:
            nr = self.piece_row + r
            nc = self.piece_col + c
            if nr < -2 or nr >= ROWS or nc < 0 or nc >= self.cols_count:
                return
            if nr >= 0 and self.field[nr][nc]:
                return
        self.piece_blocks = new_blocks

    def update(self):
        if self.game_over:
            return

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
        # Рисуем поле и фигуру в общий led_matrix
        for r in range(ROWS):
            for c in range(self.cols_count):
                color = self.color_field[r][c] if self.field[r][c] else COLOR_BLACK
                led_matrix[r+1][c + self.cols_start + 1] = color

        for r, c in self.piece_blocks:
            nr = self.piece_row + r + 1
            nc = self.piece_col + c + self.cols_start + 1
            if 0 <= nr < ROWS+2 and 0 <= nc < COLS+2:
                led_matrix[nr][nc] = self.piece_color

async def game_loop(client):
    game1 = TetrisGame(0, HALF_COLS)
    game2 = None
    led_matrix = [[COLOR_BLACK for _ in range(COLS+2)] for _ in range(ROWS+2)]
    prev_matrix = [[COLOR_BLACK for _ in range(COLS+2)] for _ in range(ROWS+2)]

    while True:
        game1.update()

        if game2 is None and game1.locked_pieces_count >= 10:
            print("🚀 Запуск второй игры после 10 упавших фигур!")
            game2 = TetrisGame(HALF_COLS, HALF_COLS)

        if game2:
            game2.update()

        # Очистка led_matrix
        for r in range(ROWS+2):
            for c in range(COLS+2):
                led_matrix[r][c] = COLOR_BLACK

        # Отрисовка обеих игр
        game1.render(led_matrix)
        if game2:
            game2.render(led_matrix)

        # Вычисляем изменённые пиксели
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

async def run():
    async with BleakClient(DEVICE_ADDRESS) as client:
        if not client.is_connected:
            print("❌ Не удалось подключиться.")
            return
        print("✅ Подключено.")
        await enter_per_led_mode(client)
        await game_loop(client)

if __name__ == '__main__':
    asyncio.run(run())
