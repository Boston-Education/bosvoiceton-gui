"""
Source: https://dev.to/stokry/monitor-files-for-changes-with-python-1npj
Modified by: RueLee
"""

import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class Invoice_File_Listener(FileSystemEventHandler):
    def __init__(self):
        self._file_event_list = set()

        self._observer = Observer()
        self._observer.schedule(self, path=r"base_generated/", recursive=False)
        self._observer.start()

    def __del__(self):
        self._observer.stop()

    def on_modified(self, event):
        self._file_event_list.add(event.src_path)
        print(f'FILEEVENT: {event.event_type} path: {event.src_path}')

    def on_created(self, event):
        self._file_event_list.add(event.src_path)
        print(f'FILEEVENT: {event.event_type} path: {event.src_path}')

    def on_deleted(self, event):
        try:
            self._file_event_list.remove(event.src_path)
        except KeyError:
            pass
        print(f'FILEEVENT: {event.event_type} path: {event.src_path}')

    def get_file_event_list(self):
        return self._file_event_list
