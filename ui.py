import logging
import argparse
import sys
import curses
from itertools import count

from modules.editor import HexEditor


logging.basicConfig(filename='log.log', level=logging.DEBUG)

INSERT_MODE = 'insert'
VIEW_MODE = 'view'

OFFSET_COLUMN_LENGTH = 8
COLUMNS = 16

ENTER_KEY = 10
ESCAPE_KEY = 27
DELETE_KEY = 330
HOME_KEY = 262
END_KEY = 358

default_bottom_bar = 'current mode: {} | h for help'
default_upper_bar = 'Offset(h)  00 01 02 03 04 05 06 07  08 09 0a 0b 0c 0d 0e 0f' \
            '   Decoded text'
help_menu = "'a' for insert mode\n'v' for view mode\n's' for save" \
            "\n'page up', 'page_down', 'home', 'end', arrows for navigation" \
            "\n'g' for goto\n'f' for find" \
            "\n'h' for open(close) help\n'q' for quit"


def str_to_bytes(value: str) -> bytes:
    return bytes([int(value[i: i + 2], 16) for i in range(0, len(value), 2)])


def is_correct_hex_symbol(value: str) -> bool:
    return 'a' <= value <= 'f' or '0' <= value <= '9'


def init_colors() -> None:
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)


class HexEditorUI:
    def __init__(self, filename: str):
        self.editor = HexEditor(filename)

        self.data = b''
        self.filename = filename

        self.current_offset = 0  # смещение, соответствующее первому байту на экране
        self.key = -1
        self.height = 0
        self.width = 0
        self.bytes_rows = 0

        self._is_in_help = False

        self.current_mode = 'view'
        self.separator = ' | '
        self.upper_bar = default_upper_bar
        self.bottom_bar = default_bottom_bar.format(self.current_mode)

        self._bottom_bar_draw_queue = []

        self._offset_str_len = OFFSET_COLUMN_LENGTH + len(self.separator)
        self._bytes_str_len = COLUMNS * 2 + COLUMNS
        self._decoded_bytes_str_len = len(self.separator) + COLUMNS
        self._total_line_len = (self._offset_str_len
                                + self._bytes_str_len
                                + self._decoded_bytes_str_len)
        self.upper_bar_underline = '-' * (self._total_line_len - 9)

        self.cursor_x = self._offset_str_len + 1
        self.cursor_y = 2

        self._x_offset = 0

        self.stdscr: curses.window = None

    def main(self, stdscr: curses.window) -> None:
        self.stdscr = stdscr
        init_colors()
        self.height, self.width = stdscr.getmaxyx()
        self.bytes_rows = self.height - 3

        while self.key != ord('q'):
            self.handle_key()
            self.stdscr.clear()
            self.draw()

            self.key = stdscr.getch()

    def draw(self) -> None:
        self._is_in_help = False
        self.stdscr.addstr(0, 0, self.upper_bar)
        self.stdscr.addstr(1, 9, self.upper_bar_underline)
        for line in range(self.height - 1):
            to_read = min(COLUMNS,
                          self.editor.file_size
                          - self.current_offset
                          - line * COLUMNS)
            self.data = self.editor.get_nbytes(
                self.current_offset + line * COLUMNS, to_read)
            self.draw_offset(line)
            self.draw_bytes(line)
            self.draw_decoded_bytes(line)
            if self.current_offset + line * COLUMNS + COLUMNS > self.editor.file_size:
                break
        if self._bottom_bar_draw_queue:
            self.bottom_bar = self._bottom_bar_draw_queue.pop()
        else:
            self.bottom_bar = default_bottom_bar.format(self.current_mode)
        self.draw_bottom_bar()
        self.draw_label()
        if self.key == ord('h'):
            self.handle_help()

        self.stdscr.move(self.cursor_y, self.cursor_x)

        self.stdscr.refresh()

    def handle_key(self) -> None:
        control_keys = {curses.KEY_UP, curses.KEY_DOWN,
                        curses.KEY_LEFT, curses.KEY_RIGHT}
        if self.key in control_keys:
            self.handle_cursor()
        # elif self.current_mode == INSERT_MODE:
        #     pass
        elif self.key == curses.KEY_NPAGE:
            self._increment_offset(self.bytes_rows * 16)
        elif self.key == curses.KEY_PPAGE:
            self._increment_offset(-self.bytes_rows * 16)
        elif self.key == ord('a'):
            self.current_mode = INSERT_MODE
            self.bottom_bar = default_bottom_bar.format(self.current_mode)
        elif self.key == ord('v'):
            self.current_mode = VIEW_MODE
            self.bottom_bar = default_bottom_bar.format(self.current_mode)
        elif self.key == ord('h'):
            if self._is_in_help:
                self.key = -1
                self._is_in_help = False
        elif self.key == ord('r'):
            self.handle_replace()
        elif self.key == ord('i'):
            self.handle_insert()
        elif self.key == ord('g'):
            self.handle_goto()
        elif self.key == ord('s'):
            self.handle_save()
        elif self.key == ord('f'):
            self.handle_search()
        elif self.key == DELETE_KEY:
            self.handle_delete()
        elif self.key == HOME_KEY:
            self._increment_offset(-self.current_offset)
        elif self.key == END_KEY:
            new_offset = (self.editor.file_size
                          - (self.bytes_rows * COLUMNS
                             - (16 - self.editor.file_size % 16)))
            self._increment_offset(new_offset - self.current_offset)
        else:
            logging.log(level=logging.DEBUG, msg=f'unknown key {self.key}')

    def draw_label(self) -> None:
        if self._is_cursor_in_bytes():
            x_coord = self._offset_str_len \
                      + self._bytes_str_len \
                      + self._x_offset + len(self.separator)
            first = self.stdscr.inch(self.cursor_y, x_coord)
            self.stdscr.addch(self.cursor_y, x_coord, first, curses.color_pair(2))
        else:
            x_coord = self._offset_str_len + self._x_offset * 3 + self._x_offset // 8 + 1
            first = self.stdscr.inch(self.cursor_y, x_coord - 1)
            second = self.stdscr.inch(self.cursor_y, x_coord)
            self.stdscr.addch(self.cursor_y, x_coord - 1, first, curses.color_pair(2))
            self.stdscr.addch(self.cursor_y, x_coord, second, curses.color_pair(2))

    def draw_offset(self, y: int) -> None:
        offset_str = '{0:0{1}x}{2}'.format(self.current_offset + y * COLUMNS,
                                           OFFSET_COLUMN_LENGTH,
                                           self.separator)
        self.stdscr.addstr(min(y + 2, self.height - 1), 0, offset_str)

    def draw_bytes(self, y: int) -> None:
        bytes_str = f"{self.data[:COLUMNS // 2].hex(' ')} " \
                    f" {self.data[COLUMNS // 2:].hex(' ')}"
        self.stdscr.addstr(min(y + 2, self.height - 1), self._offset_str_len,
                           bytes_str)

    def draw_decoded_bytes(self, y: int) -> None:
        decoded_str = '{}{}'.format(self.separator, ''.join(
            map(lambda x: chr(x) if 0x20 <= x <= 0x7e else '.', self.data)))
        self.stdscr.addstr(min(y + 2, self.height - 1),
                           self._offset_str_len + self._bytes_str_len,
                           decoded_str)

    def draw_bottom_bar(self) -> None:
        self.stdscr.attron(curses.color_pair(3))
        self.stdscr.addstr(self.height - 1, 0, self.bottom_bar)
        self.stdscr.addstr(self.height - 1, len(self.bottom_bar),
                           " " * (self.width - len(self.bottom_bar) - 1))
        self.stdscr.attroff(curses.color_pair(3))

    def handle_save(self) -> None:
        self.bottom_bar = self.filename
        self.draw_bottom_bar()
        filename = list(self.filename)
        for symbol in self.get_user_input():
            if ord(symbol) == 8 and len(filename):
                filename.pop()
            elif ord(symbol) != 8:
                filename.append(symbol)
            self.bottom_bar = ''.join(filename)
            self.draw_bottom_bar()
        self.editor.save_changes(''.join(filename))
        self._bottom_bar_draw_queue.append('saved')

    def handle_cursor(self) -> None:
        dx = dy = 0
        if self.key == curses.KEY_LEFT:
            if self.cursor_x > self._offset_str_len + 1:
                self._x_offset = (self._x_offset - 1) % COLUMNS
            if self._is_cursor_in_bytes():
                if self.cursor_x == COLUMNS + COLUMNS // 2 + 2 + self._offset_str_len:
                    # прыгаем через два пробела между блоками по 8 байт
                    dx = -4
                else:
                    dx = -3
            elif self.cursor_x == self._offset_str_len + self._bytes_str_len + 3:
                # прыгаем через разделитель после блока байт
                dx = -4
            else:
                dx = -1
        elif self.key == curses.KEY_RIGHT:
            if self.cursor_x < self._total_line_len - 1:
                if self._get_cursor_offset() + 1 == self.editor.file_size:
                    return
                self._x_offset = (self._x_offset + 1) % COLUMNS

            if self._is_cursor_in_bytes():
                if (self.cursor_x == COLUMNS + COLUMNS // 2 - 2 + self._offset_str_len
                        or self.cursor_x == self._offset_str_len + self._bytes_str_len - 1):
                    # прыгаем через два пробела между блоками по 8 байт или
                    # через разделитель после блока байт
                    dx = 4
                else:
                    dx = 3
            else:
                dx = 1
        elif self.key == curses.KEY_UP:
            dy = -1
        elif self.key == curses.KEY_DOWN:
            if self._get_cursor_offset() + COLUMNS + 1 > self.editor.file_size:
                return
            dy = 1

        self.cursor_x = min(max(self.cursor_x + dx, self._offset_str_len + 1),
                            self._total_line_len - 1)
        if self.cursor_y + dy == self.height - 1:
            self._increment_offset(COLUMNS)
        elif self.cursor_y + dy <= 1:
            self._increment_offset(-COLUMNS)
        else:
            self.cursor_y += dy

    def handle_replace(self) -> None:
        self.stdscr.move(self.cursor_y, self.cursor_x)

        if self._is_cursor_in_bytes():
            self._handle_replace_bytes()
        else:
            self._handle_replace_decoded()

    def handle_insert(self) -> None:
        if self._is_cursor_in_bytes():
            self._handle_insert_bytes()
        else:
            self._handle_insert_decoded()

    def handle_delete(self) -> None:
        self.editor.remove(self._get_cursor_offset(), 1)

    def handle_backspace(self) -> None:
        self.editor.remove(max(self._get_cursor_offset() - 1, 0), 1)
        self.key = curses.KEY_LEFT
        self.handle_cursor()

    def _convert_offset_to_x_pos(self, offset) -> int:
        offset = offset % 16
        if self._is_cursor_in_bytes():
            return self._offset_str_len + offset * 3 + offset // 8 + 1
        else:
            return self._offset_str_len \
                   + self._bytes_str_len \
                   + offset + len(self.separator)

    def _move_cursor_to_offset(self, offset):
        self.cursor_x = self._convert_offset_to_x_pos(offset)
        self._x_offset = offset % 16

    def _is_cursor_in_bytes(self) -> bool:
        return (self._offset_str_len
                <= self.cursor_x <=
                self._bytes_str_len + self._offset_str_len - 1)

    def _increment_offset(self, value: int) -> None:
        if self.current_offset + value > self.editor.file_size:
            return

        self.current_offset = max(0, self.current_offset + value)

    def _get_cursor_offset(self) -> int:
        """Offset по положению курсора"""
        return self.current_offset + (self.cursor_y - 2) * 16 + self._x_offset

    def _handle_insert_bytes(self) -> None:
        while not is_correct_hex_symbol(first_key := self.stdscr.getkey()):
            pass
        self.editor.insert(self._get_cursor_offset(), str_to_bytes(first_key))
        self.stdscr.clear()
        self.draw()

        second_key = self.stdscr.getch()
        if second_key == ENTER_KEY:
            return
        elif second_key == ESCAPE_KEY:
            self.editor.remove(self._get_cursor_offset(), 1)
            return
        else:
            second_key = chr(second_key)
            while not is_correct_hex_symbol(second_key):
                second_key = self.stdscr.getkey()
            self.editor._model.search_region(self._get_cursor_offset()).data = str_to_bytes(first_key + second_key)
            # replace ????
            self.stdscr.clear()
            self.draw()

        while (last_key := self.stdscr.getch()) not in {ENTER_KEY, ESCAPE_KEY}:
            pass
        if last_key == ENTER_KEY:
            return
        elif last_key == ESCAPE_KEY:
            self.editor.remove(self._get_cursor_offset(), 1)

    def _handle_insert_decoded(self) -> None:
        first_key = self.stdscr.getkey()
        self.editor.insert(self._get_cursor_offset(), first_key.encode())
        self.stdscr.clear()
        self.draw()

        while (last_key := self.stdscr.getch()) not in {ENTER_KEY, ESCAPE_KEY}:
            pass
        if last_key == ENTER_KEY:
            return
        elif last_key == ESCAPE_KEY:
            self.editor.remove(self._get_cursor_offset(), 1)

    def _handle_replace_bytes(self) -> None:
        before = self.stdscr.inch(self.cursor_y, self.cursor_x - 1) \
                 + self.stdscr.inch(self.cursor_y, self.cursor_x)

        while not is_correct_hex_symbol(first_key := self.stdscr.getkey()):
            pass
        self.stdscr.addch(self.cursor_y, self.cursor_x, first_key)
        self.stdscr.addch(self.cursor_y, self.cursor_x - 1, '0')
        self.stdscr.refresh()

        second_key = self.stdscr.getch()
        if second_key == ENTER_KEY:
            self.editor.replace(self._get_cursor_offset(),
                                str_to_bytes(first_key))
            return
        elif second_key == ESCAPE_KEY:
            self.stdscr.addstr(self.cursor_y, self.cursor_x - 1, chr(before))
            return
        else:
            second_key = chr(second_key)
            while not is_correct_hex_symbol(second_key):
                second_key = self.stdscr.getkey()
            self.stdscr.addstr(self.cursor_y, self.cursor_x - 1, first_key)
            self.stdscr.addstr(self.cursor_y, self.cursor_x, second_key)

        self.stdscr.move(self.cursor_y, self.cursor_x)
        while (last_key := self.stdscr.getch()) not in {ENTER_KEY, ESCAPE_KEY}:
            pass
        if last_key == ENTER_KEY:
            self.editor.replace(self._get_cursor_offset(),
                                str_to_bytes(first_key + second_key))
        elif last_key == ESCAPE_KEY:
            self.stdscr.addstr(self.cursor_y, self.cursor_x - 1, chr(before))

    def _handle_replace_decoded(self) -> None:
        before = self.stdscr.inch(self.cursor_y, self.cursor_x)

        first_key = self.stdscr.getkey()
        self.stdscr.addch(self.cursor_y, self.cursor_x, first_key)
        self.stdscr.refresh()

        self.stdscr.move(self.cursor_y, self.cursor_x)
        while (last_key := self.stdscr.getch()) not in {ENTER_KEY, ESCAPE_KEY}:
            pass
        if last_key == ENTER_KEY:
            self.editor.replace(self._get_cursor_offset(), first_key.encode())
        elif last_key == ESCAPE_KEY:
            self.stdscr.addstr(self.cursor_y, self.cursor_x - 1, chr(before))

    def handle_help(self) -> None:
        self._is_in_help = True
        lines = help_menu.split('\n')
        self.stdscr.attron(curses.color_pair(3))
        for i, line in enumerate(lines):
            self.stdscr.addstr(2 + i, 0,
                               line + ' ' * (self._total_line_len - len(line)))
        self.stdscr.attroff(curses.color_pair(3))

    def handle_goto(self) -> None:
        user_input = []
        self.bottom_bar = 'goto (h): '
        self.draw_bottom_bar()
        for symbol in self.get_user_input(filter=is_correct_hex_symbol):
            if ord(symbol) == 8 and len(user_input):
                user_input.pop()
            elif ord(symbol) != 8:
                user_input.append(symbol)
            self.bottom_bar = f'goto (h): {"".join(user_input)}'
            self.draw_bottom_bar()
        offset = int("".join(user_input), 16)
        self._increment_offset((offset - offset % 16) - self.current_offset)
        self._move_cursor_to_offset(offset)

    def handle_search(self) -> None:
        user_input = []
        self.bottom_bar = 'search (h): '
        self.draw_bottom_bar()
        counter = count()
        for symbol in self.get_user_input(filter=is_correct_hex_symbol):
            if next(counter) % 2 - 1:
                if ord(symbol) == 8 and len(user_input) >= 2:
                    user_input[-1] = user_input[-2]
                    user_input[-2] = '0'
                    next(counter)
                elif ord(symbol) != 8:
                    user_input.append('0')
                    user_input.append(symbol)
            else:
                if ord(symbol) == 8 and len(user_input) >= 2:
                    del user_input[-2:]
                    next(counter)
                elif ord(symbol) != 8:
                    del user_input[-2]
                    user_input.append(symbol)
            self.bottom_bar = f'search (h): {"".join(user_input)}'
            self.draw_bottom_bar()

        query = ''.join(user_input)
        logging.log(msg=f'trying to find {str_to_bytes(query)}', level=logging.DEBUG)
        if (offset := self.editor.search(str_to_bytes(query))) == -1:
            logging.log(msg=f'query {query} not found', level=logging.DEBUG)
            self._bottom_bar_draw_queue.append('not found')
            return
        logging.log(msg=f'found at offset {offset}', level=logging.DEBUG)
        self.current_offset = offset - offset % COLUMNS
        self._move_cursor_to_offset(offset)

    def get_user_input(self, filter=lambda x: True) -> str:
        """Считывает пользовательский ввод до нажатия enter. Если передан
           filter, то считывает только символы, удовлетворяющие filter
           и кнопку backspace"""
        while (key := self.stdscr.getkey()) != '\n':
            if filter(key) or ord(key) == 8:
                yield key


def main():
    parser = argparse.ArgumentParser(description="Hex editor")
    # app = HexEditorUI(sys.argv[1])
    app = HexEditorUI('alabai.png')
    curses.wrapper(app.main)


if __name__ == '__main__':
    main()
