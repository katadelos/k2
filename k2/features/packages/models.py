"""Package requests, transaction previews and rows exposed to QML."""

from dataclasses import asdict

from PyQt5.QtCore import QAbstractListModel, Qt

from ...core.packages import PackageRecord


class PackageListModel(QAbstractListModel):
    RecordRole = Qt.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def roleNames(self):
        return {self.RecordRole: b"record"}

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if (
            index.isValid()
            and 0 <= index.row() < len(self._rows)
            and role == self.RecordRole
        ):
            return asdict(self._rows[index.row()])
        return None

    def replace(self, rows):
        rows = [PackageRecord.from_mapping(row) for row in rows]
        if rows == self._rows:
            return
        if [row.name for row in rows] == [row.name for row in self._rows]:
            previous, self._rows = self._rows, rows
            for i, (old, new) in enumerate(zip(previous, rows, strict=True)):
                if old != new:
                    self.dataChanged.emit(
                        self.index(i), self.index(i), [self.RecordRole]
                    )
        else:
            self.beginResetModel()
            self._rows = rows
            self.endResetModel()
