#!/usr/bin/env python3
import sys, os, signal, psutil, logging
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QComboBox, QCheckBox
from PyQt5.uic import loadUi
from PyQt5.QtCore import QThread, QObject, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from python_src.src import leagueinstaller

class GuiLogHandler(QObject, logging.Handler):
    new_record = pyqtSignal(object)

    def __init__(self, parent):
        super().__init__(parent)
        super(logging.Handler).__init__()
        formatter = Formatter('%(levelname)s: %(message)s', '%d/%m/%Y %H:%M:%S')
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        self.new_record.emit(msg) # <---- emit signal here

class Formatter(logging.Formatter):
    def formatException(self, ei):
        result = super(Formatter, self).formatException(ei)
        return result

    def format(self, record):
        s = super(Formatter, self).format(record)
        if record.exc_text:
            s = s.replace('\n', '')
        return s

class Installer(QMainWindow):
    def __init__(self):
        super(Installer, self).__init__()
        # Hacky workaround so the AppImage works
        try:
            loadUi("python_src/ui/installer.ui", self)
        except:
            loadUi("/usr/share/lolforlinux/ui/installer.ui", self)
        self.setFixedSize(self.size())
        self.setWindowTitle('League of Legends Installer')
        self.install_button.clicked.connect(self.installer_code)
        self.cancelButton.clicked.connect(self.cancel_installation)
        self.install_button.setEnabled(True)
        self.githubButton.clicked.connect(self.open_github)
        self.cancelButton.setEnabled(False)
        self.stackedWidget.setCurrentWidget(self.welcome)

        self.nextWelcome.clicked.connect(self.regionWidget)
        self.nextRegion.clicked.connect(self.optionsWidget)

    def regionWidget(self):
        self.stackedWidget.setCurrentWidget(self.region)

    def optionsWidget(self):
        self.stackedWidget.setCurrentWidget(self.options)

    def open_github(self):
        url = "https://github.com/kassindornelles/lol-for-linux-installer/issues"
        QDesktopServices.openUrl(QUrl(url))

    def cancel_installation(self):
        # Get the PID of the current process
        pid = os.getpid()

        # Get a list of all child processes
        children = psutil.Process(pid).children(recursive=True)

        # Terminate all child processes
        for child in children:
            child.send_signal(signal.SIGTERM)

        # Terminate the main application process
        os.kill(pid, signal.SIGTERM)

    def addPlainText(self, text: str):
        self.textOuput.appendPlainText(text)

    def setup_logger(self):

        # Send info logs to textOutput
        handler = GuiLogHandler(self)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        handler.new_record.connect(self.textOutput.append)

        # Send debug logs to stdout
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(Formatter('%(levelname)s: %(message)s\n', '%d/%m/%Y %H:%M:%S'))
        stream_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(stream_handler)

    def installer_code(self):
        self.game_main_dir = QFileDialog.getExistingDirectory(self, 'Where do you want to install the game?')
        while self.game_main_dir and os.path.abspath(self.game_main_dir) == os.path.expanduser("~"):
            # If the user selected their home directory, display an error message
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setText("Cannot install the game directly in the home directory.")
            msg_box.setInformativeText("Please create a folder in your home directory instead so we can use it")
            msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            msg_box.setDefaultButton(QMessageBox.Ok)
            if msg_box.exec_() == QMessageBox.Ok:
                # If the user clicks "Ok", allow them to select a different directory
                self.game_main_dir = QFileDialog.getExistingDirectory(self, 'Where do you want to install the game?')
            else:
                # If the user clicks "Cancel", exit the loop and do not set the directory
                self.game_main_dir = None

        # Check if the selected directory is inside the user's home directory
        if not os.path.abspath(self.game_main_dir).startswith(os.path.expanduser("~")):
            # If not, display an error message and prompt the user to select a different directory
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setText("Invalid directory selected.")
            msg_box.setInformativeText("Please select a directory within your home directory.")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.setDefaultButton(QMessageBox.Ok)
            msg_box.exec_()
            self.game_main_dir = QFileDialog.getExistingDirectory(self, 'Where do you want to install the game?')

        self.stackedWidget.setCurrentWidget(self.installing)

        if self.game_main_dir:
            self.cancelButton.show()
            self.cancelButton.setEnabled(True)
            self.checkShortcut.setEnabled(False)
            self.welcomelabel.setText("We are installing the game for you...")
            self.install_button.setEnabled(False)
            self.languageComboBox.setEnabled(False)
            self.regionLabel.setEnabled(False)
            self.checkPrime.setEnabled(False)

            # Get the game download link and apply region based on text from .ui file
            region_map = {
                "BR (BR1) - Brazil": "br",
                "LAN (LA1) - Latin America North": "la1",
                "LAS (LA2) - Latin America South": "la2",
                "NA (NA1) - North America": "na",
                "OCE (OCE/OC1) - Oceania": "oc1",
                "RU (RU1) - Russia": "ru",
                "EUW (EUW1) - Europe West": "euw",
                "EUNE (EUN1) - Europe Nordic & East": "eune",
                "TR (TR1) - Turkey": "tr",
                "JP (JP1) - Japan": "jp",
                "KR (KR) - Republic of Korea": "kr",
            }

            selected_lang = self.languageComboBox.currentText()
            game_link = "https://lol.secure.dyn.riotcdn.net/channels/public/x/installer/current/live.{}.exe"

            region = region_map.get(selected_lang, "na")
            game_region_link = game_link.format(region)

            self.setup_logger()
            scrollbar = self.textOutput.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

            self.thread = QThread()
            self.worker = Worker(self.game_main_dir, game_region_link, self.checkShortcut.isChecked(), self.checkPrime.isChecked())
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.thread.finished.connect(self.finish_installation)
            self.thread.start()
            self.thread.quit()
        else:
            # Handle case where user pressed cancel
            print("User pressed cancel")

    def finish_installation(self):

        QApplication.quit()


class Worker(QObject):
    def __init__(self, game_main_dir, game_region_link, create_shortcut, enable_prime):
        super().__init__()
        self.game_main_dir = game_main_dir
        self.game_region_link = game_region_link
        self.create_shortcut = create_shortcut
        self.enable_prime = enable_prime

    def run(self):
        leagueinstaller.league_install_code(self.game_main_dir, self.game_region_link, self.create_shortcut, self.enable_prime)
        QApplication.quit()

class QTextEditLogger(logging.Handler, QObject):
    appendPlainText = pyqtSignal(str)

if __name__ == '__main__':
    app = QApplication(sys.argv)

    if os.getuid() == 0:
        msg_box = QMessageBox()
        msg_box.setText("Don't run this as sudo user")
        msg_box.exec_()
        sys.exit(1)

    installer = Installer()
    installer.show()
    sys.exit(app.exec_())
