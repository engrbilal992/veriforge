"""VeriForge — entry point.

`python main.py`                  -> launch the GUI
`python main.py <cli args...>`    -> run the CLI (new/add/gen/sim/open/...)
"""
import sys


def main():
    # No args -> GUI. Any args -> CLI dispatcher.
    if len(sys.argv) > 1:
        from app.cli import main as cli_main
        sys.exit(cli_main(sys.argv[1:]))
    from PySide6.QtWidgets import QApplication
    from app.main_window import MainWindow
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
