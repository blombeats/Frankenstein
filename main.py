from PySide2 import QtCore, QtWidgets, QtGui
from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap

from blom import init_logger, timer
import sqlite_utils as sql
import sys
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QApplication, QMainWindow, QDialog, QMessageBox, QTableWidget, QListWidgetItem, QLineEdit, \
    QFileDialog
from PySide2.QtCore import QFile, QIODevice, QSize, Qt, QCoreApplication, QRectF, Slot
import re
from ui_loader import load_ui
from time import sleep

l = init_logger('frankenstein')
db = sql.Database('database.db')


def infomsg(parent, msg: str):
    QMessageBox.information(parent, 'Title', msg, QMessageBox.Ok)


def errormsg(parent, msg: str = 'test'):
    QMessageBox.critical(parent, "Title", msg, QMessageBox.Ok)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        loader = QUiLoader()
        load_ui('ui.ui', self)
        self.progressBar.setValue(12)
        self._connectAll()
        self._refresh_ui()
        self.filterinput.setText('png jpeg jpg exr tif tiff')

    def _refresh_ui(self):
        refresh_timer = timer()
        l.info(f'Refreshing UI')

        self.watchlist.clear()
        self.fileslist.clear()

        self.watchlist.addItems(self._get_watchlist())

        QCoreApplication.processEvents()
        self.update()
        l.info(f'Refreshed UI in {refresh_timer}')

    def _connectAll(self):
        self.watch_refresh.clicked.connect(self._refresh_ui)
        self.watchlist.itemSelectionChanged.connect(self.fileslist_list_files)
        self.watch_add.clicked.connect(self.watchlist_add_folder)
        self.watch_remove.clicked.connect(self.watchlist_remove_selected)
        self.watch_scan_all.clicked.connect(self.watchlist_scan_all)
        self.watch_scan_selected.clicked.connect(self.watchlist_scan_selected)
        self.fileslist.itemSelectionChanged.connect(self.imageviever_show_image)
        self.btn_filter.clicked.connect(self.fileslist_list_files)
        self.checkBoxGroupImageSequences.stateChanged.connect(self.groupImageSequences)

    def test(self):
        print("hahahaha")

    def _table_to_list(self, folder):
        timer_scan_folder_db = timer()
        l.info(f'Looking in db for {str(folder)}')
        files = list(db[str(folder)].rows_where(select="path"))
        files_list = [x['path'] for x in files]
        l.info(f'Took {timer_scan_folder_db}, returning files')
        return files_list


    def _get_watchlist(self):
        return [str(x.name) for x in db.tables]

    def updateProgressBar(self, val):
        # TODO do this in thread instead
        l.info(f'Setting progressbar to something')
        self.progressBar.setValue(val)

    def groupImageSequences(self):

        paths=sortImageSequence.combinedPaths(self.currentFiles)

        self.fileslist.clear()
        self.fileslist.addItems(paths)
        self.number_of_files.setText(f'{len(paths)} files')
        self.update()

    def fileslist_list_files(self):
        timeer = timer()
        try:
            selected = self.watchlist.selectedItems()[0].text()
        except:
            l.warning('Skipping fileslist_list_files selected couldnt be found')
            return
        l.info(f'Listing files for {selected}')

        listan = self._table_to_list(selected)

        # Filtering
        filtertext = self.filterinput.text()

        if filtertext:
            filters = filtertext.split()
            l.info(f'filters: {filters}')

            newlistan = []

            for filt in filters:
                newlistan.extend([x for x in listan if x.endswith(filt.lower())])
                newlistan.extend([x for x in listan if x.endswith(filt.upper())])
            listan = newlistan

        number_of_files = len(listan)

        self.currentFiles = listan

        self.fileslist.clear()
        self.fileslist.addItems(listan)
        self.number_of_files.setText(f'{number_of_files} files')
        self.update()

        l.info(f'Took {timeer}')

    def watchlist_add_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.tr("Load Folder"))

        if path:

            clock = timer()
            l.info(f'Adding {path} to db')
            db[path].create({'path': str})
            l.info(f"Added {1} folder in {clock}")
            self._refresh_ui()

        else:
            l.info('canceldd adding folder')

    def watchlist_remove_selected(self):
        # Can be optimized by removing it from gui only and db instead of refreshing the whole list from db after removing it.

        selected = self.watchlist.selectedItems()[0].text()

        l.info(f'Removing selected table: {selected}')
        db[selected].drop()
        db.conn.commit()

        self.refresh_ui()

    def watchlist_scan_selected(self):
        selected = self.watchlist.selectedItems()[0].text()
        l.info(f"Scanning selected {selected}")
        timer_scan_total = timer()

        self.updateProgressBar(0)
        l.info('#' * 50)
        timer_scan = timer()
        l.info(f'Dropping folder...')
        db[selected].drop()
        db.conn.commit()
        files_folders = list(Path(selected).rglob("*"))
        l.info(f"Found {len(files_folders)} files and folders total in {timer_scan}")

        # l.info('TODO cleaning db if exists')

        l.info(f'Checking which is file and folder (can prob be optimized)')
        timer_filefolder = timer()
        files = [x for x in files_folders if x.is_file()]
        l.info(f'Found {len(files)} files')
        l.info(f'Found {len(files_folders) - len(files)} folders')
        files_clean = [{'path': str(x)} for x in files]
        l.info(f'Took {timer_filefolder}')

        l.info('Writing to db')
        timer_db_write = timer()
        db[str(selected)].insert_all(files_clean)
        l.info(f'Took {timer_db_write}')

        l.info(f'Total took {timer_scan_total} refreshing...')
        self.updateProgressBar(100)
        self._refresh_ui()

    def watchlist_scan_all(self):
        watchlist = self._get_watchlist()
        l.info(f"Scanning all {len(watchlist)} folders in watchlist")
        timer_scan_all_total = timer()

        for i, folder in enumerate(watchlist):
            self.updateProgressBar((i + 1) / len(watchlist) * 100)
            l.info('#' * 50)
            l.info(f"Scanning folder {i} of {len(watchlist)}  {folder}")
            timer_scan = timer()
            l.info(f'Dropping folder...')
            db[folder].drop()
            db.conn.commit()
            files_folders = list(Path(folder).rglob("*"))
            l.info(f"Found {len(files_folders)} files and folders total in {timer_scan}")

            # l.info('TODO cleaning db if exists')

            l.info(f'Checking which is file and folder (can prob be optimized)')
            timer_filefolder = timer()
            files = [x for x in files_folders if x.is_file()]
            l.info(f'Found {len(files)} files')
            l.info(f'Found {len(files_folders) - len(files)} folders')
            files_clean = [{'path': str(x)} for x in files]
            l.info(f'Took {timer_filefolder}')

            l.info('Writing to db')
            timer_db_write = timer()
            db[str(folder)].insert_all(files_clean)
            l.info(f'Took {timer_db_write}')

        l.info(f'Total took {timer_scan_all_total} refreshing...')
        self.updateProgressBar(100)
        self._refresh_ui()

    def imageviever_show_image(self):

        timeer = timer()
        selected = self.fileslist.selectedItems()[0].text()
        l.info(f'Showing image for {selected}')

        actualImage = QtGui.QImage(selected)
        pixmap = QtGui.QPixmap(actualImage)

        pixmap = pixmap.scaled(500, 500, QtCore.Qt.KeepAspectRatio)

        self.labelimage.setPixmap(pixmap)
        self.labelimage.setScaledContents(True)
        l.info(f'Took {timeer}')


def scan_folder_disk(folder):
    timer_scan_folder_disk = timer()
    l.info(f'Adding folder {str(folder)}')
    l.warning('Deleing previous records')
    db[folder].delete_where()
    l.info('Deleted')
    l.info(f'Scanning...')
    files_folders = list(folder.rglob("*"))
    l.info(f'Scan took {timer_scan_folder_disk}')
    return files_folders

class sortImageSequence:
    regexPattern = r'\.[0-9]{1,100}\.'

    @staticmethod
    def _getFrameNumber(path: str):
        """
        Returns the frameNumber and regex match based on path

        re.search(r'\.[0-9]{1,100}\.[a-z]+',x) #match frames and extension
        re.search(r'\.[0-9]{1,100}\.',x) #match frames
        """
        match = re.search(sortImageSequence.regexPattern, str(path))  # match frames
        if match:
            match_clean = match.group()
            match_clean = match_clean[1:-1]  # remove the dots
            match_clean = int(match_clean)
            return (match_clean, match)
        else:
            return None

    @staticmethod
    def combinedPaths(paths: list) -> str:
        """
        Returns a string with combined framerange from the inserted list
        """

        # Find all sequences
        sequences = {
        }

        for path in paths:
            frame = sortImageSequence._getFrameNumber(path)
            if frame:
                delrange = frame[1].regs[0]
                number = int(frame[1].group()[1:-1])
                numberlength = len(str(frame[0]))
                outstrtemp = path[:delrange[0]] + "." + ("#" * numberlength) + "." + path[delrange[1]:]

                try:
                    # Try if list already exists
                    sequences[outstrtemp]
                except KeyError:
                    sequences[outstrtemp] = {}

                sequences[outstrtemp][path] = {'delrange': delrange,
                                               'numberlength': numberlength,
                                               'number': number}

        # Find start end sequences
        for key, item in sequences.items():
            frames = [x['number'] for y, x in item.items()]
            sequences[key]["startframe"] = min(frames)
            sequences[key]["endframe"] = max(frames)

        # Add these to list:
        for key, item in sequences.items():

            paths.append(key)
            filestoremove = [x for x in item.keys() if x != "startframe" and x != 'endframe']

            for file in filestoremove:
                del paths[paths.index(file)]

        # remove files to list

        paths.sort()

        return paths


"""
paths=self.currentFiles

"""

if __name__ == "__main__":
    watchlist = [Path("C:\Assets\Cykelklubben\Leaves"), Path("C:\Assets\Cykelklubben\License"),
                 Path("Y:\Models"), Path("Y:\Footage"), Path("Y:\Other"), Path("Y:\HDRI"), Path("Y:\previews"),
                 Path("Y:\Sound FX"), Path("Y:\Textures")]

    app = QApplication(sys.argv)
    self = MainWindow()
    self.show()
    sys.exit(app.exec_())



