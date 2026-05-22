#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

import os
import locale
import docsearch
import docextract

locale.bindtextdomain('pardus-belgeara', '/usr/share/locale')
locale.textdomain('pardus-belgeara')

GLADE_FILE = os.path.dirname(os.path.abspath(__file__)) + "/../ui/MainWindow.glade"


class pardusbelgeara:
    def __init__(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(GLADE_FILE)

        # -------Widget referansları-------
        # Main Window
        self.mainwindow = self.builder.get_object("mainwindow")  # home window

        # -------Signals-------
        # Main Window
        self.mainwindow.connect("destroy", self._on_destroy)
        self.mainwindow.show_all()

    def _on_destroy(self, widget):
        Gtk.main_quit()

app = pardusbelgeara()
Gtk.main()

