# main.py

import sys
from PyQt5.QtWidgets import QApplication
from gui import PlayerGUI

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = PlayerGUI()
    gui.show()
    sys.exit(app.exec_())
