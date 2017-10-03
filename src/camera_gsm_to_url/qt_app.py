import sys
import threading
import queue
from PyQt5.QtWidgets import *


class QtApp(threading.Thread):
    form_queue = queue.Queue()

    def __init__(self):
        threading.Thread.__init__(self, daemon=True)
        self.start()

    def run(self):
        self.qt = QApplication(sys.argv)
        while True:
            if not self.form_queue.empty():
                form, func, args = self.form_queue.get()
                self.form = form(args)
                if func is not None:
                    getattr(self.form, func)()
                self.form.show()
                self.form_queue.task_done()
                self.qt.exec_()

    def open(self, form, func=None, *args):
        self.form_queue.put((form, func, args))
        self.form_queue.join()
        return self.form

    def close(self):
        try:
            self.form.close()
        except:
            pass

qt_app = QtApp()
