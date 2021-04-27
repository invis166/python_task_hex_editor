import os.path
from buffer import DataBuffer
from filemodel import FileModel, FileRegion, EditedFileRegion


class HexEditor:
	def __init__(self, filename: str):
		self._fp = open(filename, 'r+b')
		self._model = FileModel(os.path.getsize(filename))
		self._buffer = DataBuffer(self._model, self._fp)

	def get_nbytes(self, offset: int, count: int) -> list:
		return self._buffer.read_nbytes(offset, count)

	def replace_bytes(self, offset: int, data: list) -> None:
		self._model.replace(offset, data)

	def insert_bytes(self, offset: int, data: list) -> None:
		self._model.insert(offset, data)

	def remove_bytes(self):
		pass

	def save_changes(self):
		for region in self._model.file_regions:
			if isinstance(region, EditedFileRegion):
				self._fp.seek(region.start)
				self._fp.write(region.data)

	def __del__(self):
		self.fp.close()


if __name__ == '__main__':
	pass
