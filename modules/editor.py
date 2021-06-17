import os.path
from modules.buffer import DataBuffer
from modules.filemodel import FileModel, FileRegion, EditedFileRegion


class HexEditor:
    def __init__(self, filename: str, is_readonly=False):
        if is_readonly:
            self._fp = open(filename, 'rb')
        else:
            self._fp = open(filename, 'r+b')
        self._model = FileModel(os.path.getsize(filename))
        self._buffer = DataBuffer(self._model, self._fp)

    def get_nbytes(self, offset: int, count: int) -> bytes:
        return bytes(self._buffer.read_nbytes(offset, count))

    def replace(self, offset: int, data: bytes) -> None:
        self._model.replace(offset, data)

    def insert(self, offset: int, data: bytes) -> None:
        self._model.insert(offset, data)

    def remove(self, offset: int, count: int) -> None:
        self._model.remove(offset, count)

    def save_changes(self):
        for region in self._model.file_regions:
            if isinstance(region, EditedFileRegion):
                self._fp.seek(region.start)
                self._fp.write(region.data)
            elif (region.original_start != region.start
                  or region.original_end != region.end):
                self._fp.seek(region.start)
                self._fp.write(self.get_nbytes(region.start, region.length))
        self._fp.flush()

        self._model = FileModel(self._model.file_size)
        self._buffer._file_model = self._model

    def search(self, query: bytes) -> int:
        """Поиск подстроки в строке через полиномиальный хэш"""
        # нет проверки на длину входных данных
        p = 1000
        max_power = p ** (len(query) - 1)
        query_hash = 0
        substring_hash = 0
        for i in range(len(query)):
            query_hash = query_hash * p + query[i]
            substring_hash = substring_hash * p + self.get_nbytes(i, 1)[0]

        for i in range(len(query), self.file_size + 1):
            if query_hash == substring_hash:
                if query == self.get_nbytes(i - len(query), len(query)):
                    return i - len(query)
            if i == self.file_size:
                return -1
            substring_hash -= max_power * self.get_nbytes(i - len(query), 1)[0]
            substring_hash = substring_hash * p + self.get_nbytes(i, 1)[0]

        return -1

    def exit(self):
        self._fp.close()

    @property
    def file_size(self) -> int:
        return self._model.file_size

    def __del__(self):
        self.exit()


if __name__ == '__main__':
    pass
