#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, Gdk, GLib

import os
import subprocess
import threading
import queue
import sys
import time
import locale
from locale import gettext as _
from pathlib import Path

import docdatabase
from docsearch_functions import files_list, check_database, embedfile, search

locale.bindtextdomain('pardus-docsearch', '/usr/share/locale')
locale.textdomain('pardus-docsearch')

GLADE_FILE = os.path.dirname(os.path.abspath(__file__)) + "/../ui/MainWindow.glade"


class pardusdocsearch:
    def __init__(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(GLADE_FILE)

        # -------Widget references-------
        # Main Window
        self.mainwindow = self.builder.get_object("mainwindow")  # home window
        self.listbox    = self.builder.get_object("listbox")  # listbox object
        self.mainstack      = self.builder.get_object("main_stack")
        self.scrolled_window = self.builder.get_object("scrolled_window")  # scrolled window
        self.status_label1    = self.builder.get_object("status_label1")  # status label
        self.info_label     = self.builder.get_object("info_label")  # total files
        self.warning_label1    = self.builder.get_object("warning_label1")  # warning label
        self.warning_label2    = self.builder.get_object("warning_label2")  # warning label
        self.searchbutton    = self.builder.get_object("searchbutton")  # search button
        self.listagain_btn   = self.builder.get_object("list_again")  # list again button
        self.search_entry    = self.builder.get_object("search_entry")  # search entry box
        self.aboutbtn        = self.builder.get_object("about_button")  # about button

        # About Window
        self.about_dialog = self.builder.get_object("about_dialog")  # about screen

        # -------Signals-------
        # Main Window
        self.mainwindow.connect("destroy", self._on_destroy)
        self.searchbutton.connect("clicked", self.on_search)
        self.listagain_btn.connect("clicked", self.on_list_again)
        self.aboutbtn.connect("clicked", self._on_aboutdialog)
        self.mainwindow.show_all()


        # first steps to take before the software screen appears
        check_database()
        homefolder = Path.home()
        self.dbpath = homefolder / ".cache" / "pardus-docsearch" / "docdatabase.db"  # location where the database will be placed
        self.listagain_btn.hide()
        self.warning_label2.hide()  # hide warning label
        self.search_entry.set_placeholder_text(_("Enter the content:"))  # placeholder
        self.warning_label1.set_label(_("The process of writing files from your computer to the database may take a long time\nDo not close the screen until the process is complete"))  # warning message is being printed
        self.search_entry.set_width_chars(40)  # length of the text box
        self.scrolled_window.set_min_content_height(400)  # the height of the list window is being adjusted in pixels
        self.mainstack.set_visible_child_name("page0")
        self.db_total_files = docdatabase.totalfiles(self.dbpath)
        GLib.idle_add(self.start_background_once)  # the process will run in the background immediately after the application starts


        # process queue structure
        self.doc_queue = queue.Queue()
        self.db_queue  = queue.Queue()

        self._consuming   = False
        self.listbox_done = False  # once objects are entered into the list box, this variable is set to "True" when the process is complete
        self.embed_done   = False  # This variable is set to "True" after the database embedding process is complete


    def start_background_once(self):
        # start worker thread
        threading.Thread(target=self.docs_list_process, daemon=True).start()  # listing files, printing to database
        threading.Thread(target=self.db_embed_worker, daemon=True).start()  # write operation to the database

        # start the loop that consumes the queue in the main thread
        if not self._consuming:
            self._consuming = True
            GLib.timeout_add(100, self._consume_queue)  # consume at 100 ms intervals
        return False


    # listing files, printing to database
    def docs_list_process(self):
        for f in files_list():  # files_list() --- (may be CPU/IO bound)
            self.doc_queue.put(f)
            self.db_queue.put(f)
        self.listbox_done = True
        # report to the main cycle that production is complete
        self.doc_queue.put(None)
        self.db_queue.put(None)


    # write operation to the database
    def db_embed_worker(self):
        conn, cur = docdatabase.get_conn(self.dbpath)
        srcpath = cur.execute("SELECT source_name FROM documents").fetchall()
        srcpath = [r[0] for r in srcpath]

        while True:
            doc_path = self.db_queue.get()  # the process will not proceed to other operations until data arrives from the db_queue queue
            if doc_path is None:
                break
            # the existence of the same data in the database is checked
            if doc_path in srcpath:
                continue
            else:
                self.status_label1.set_label(_("Writing:\n")+doc_path)
                embedfile(doc_path)  # the process of writing to the database is being performed
        self.embed_done = True


    # queue consume loop
    def _consume_queue(self):
        processed_any = False
        while True:
            try:
                doc_path = self.doc_queue.get_nowait()
            except queue.Empty:
                break

            if doc_path is None:
                self.listbox_done = True
                break

            filename = os.path.basename(doc_path)
            tooltip_txt = _("File full path: ")+doc_path
            row = self.create_row(filename, doc_path, tooltip_txt, "0")  # regardless of all sources, page number 0 is returned
            self.listbox.add(row)

        # the main screen will not be accessed until the result of both operations is True, and `return True` will continue to run
        if self.listbox_done and self.embed_done:
            self.mainstack.set_visible_child_name("mainbox")
            self.info_label.set_label(_("Total files: ")+str(self.db_total_files))
            self.listbox.show_all()
            return False

        return True


    # row function to be created for each data point
    def create_row(self, filename, fullpath, tooltip_txt, pagenum):
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        # ICON box
        if filename[-3:] == "pdf":
          image = Gtk.Image.new_from_icon_name("application-pdf", Gtk.IconSize.BUTTON)
          image.set_halign(Gtk.Align.START)
        elif filename[-3:] == "txt":
          image = Gtk.Image.new_from_icon_name("text-x-generic", Gtk.IconSize.BUTTON)
          image.set_halign(Gtk.Align.START)
        else:
          image = Gtk.Image.new_from_icon_name("text-x-generic", Gtk.IconSize.BUTTON)
          image.set_halign(Gtk.Align.START)

        # TEXT box and labels
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_halign(Gtk.Align.CENTER)
        label_name = Gtk.Label(label=filename)
        label_name.set_xalign(0)

        # the file path text is being shortened
        short_path = fullpath[:50] + "..." if len(fullpath) > 50 else fullpath
        label_path = Gtk.Label(label=short_path)
        label_path.set_xalign(0)

        # BUTTON box and buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        button_box.set_halign(Gtk.Align.END)
        button_open = Gtk.Button(label=_("Open"))
        button_opndir = Gtk.Button(label=_("Open in directory"))

        # -------Signals-------
        button_open.connect("clicked", self.on_open_file, fullpath, pagenum)
        button_opndir.connect("clicked", self.on_open_in_directory, fullpath)
        # ---------------------

        text_box.pack_start(label_name, False, False, 0)
        text_box.pack_start(label_path, False, False, 0)

        button_box.pack_start(button_open, False, False, 0)
        button_box.pack_start(button_opndir, False, False, 0)

        # ROW placement (efforts were made to minimize gaps)
        row_box.pack_start(image, False, False, 3)
        row_box.pack_start(text_box, False, False, 3)
        row_box.pack_end(button_box, False, False, 3)

        row_box.set_tooltip_text(tooltip_txt)

        return row_box


    # file open
    def on_open_file(self, button, fullpath, pagenum):
        if fullpath[-3:] == "pdf":
          subprocess.run(["evince", "-i", pagenum, fullpath])  # in the Pardus operating system, `evince` is installed as the document viewer software
        else:
          subprocess.run(["xdg-open", fullpath])


    # file open in directory
    def on_open_in_directory(self, button, fullpath):
        subprocess.run(["thunar", fullpath])


    # ----SEARCH PROCESS----
    # search button
    def on_search(self, button):
        self.warning_label2.hide()  # it is closed if an error message is displayed
        searchcontent = self.search_entry.get_text()
        if len(searchcontent) == 0:
            self.warning_label2.show()
            self.warning_label2.set_label("Enter some text to search!")
            return False
        self.mainstack.set_visible_child_name("page1")
        # Start the thread to run in the background
        thread = threading.Thread(target=self.search_process, args=(searchcontent,), daemon=True)
        thread.start()

    def search_process(self, searchcontent):
        output = search(searchcontent)  # searching content
        GLib.idle_add(self.update_search_listbox, output)

    def update_search_listbox(self, output):
        # clearing a populated listbox object
        for row in self.listbox.get_children():
          row.destroy()

        # writing the results to a listbox object
        for f in output:
            srcname = os.path.basename(f["source"])
            if srcname[-3:] == "pdf":
                row = self.create_row(srcname, f["source"], _("Content:\n")+f["chunk"], str(f["pagenum"]))  # the function receives the page number of the output found in the search results (PDF files)
            else:
                row = self.create_row(srcname, f["source"], _("Content:\n")+f["chunk"], "0")
            self.listbox.add(row)
        self.search_process_done()

    def search_process_done(self):
        self.mainstack.set_visible_child_name("mainbox")
        self.listagain_btn.show()  # to return to the entire file list after the search is complete, the button must be active
        self.listbox.show_all()
        return False  # 'GLib.idle_add' callback should not be called again
    # ----------------------


    # ----LIST AGAIN PROCESS----
    # list again button
    def on_list_again(self, button):
        self.mainstack.set_visible_child_name("page2")
        # Start the thread to run in the background
        thread = threading.Thread(target=self.list_again_process, daemon=True)
        thread.start()

    def list_again_process(self):
        files = files_list()
        GLib.idle_add(self.update_listbox, files)


    def update_listbox(self, files):
        for row in self.listbox.get_children():
            self.listbox.remove(row)
        for f in files:
            row = self.create_row(
                os.path.basename(f),
                f,
                _("File full path: ") + f,
                "0"
            )
            self.listbox.add(row)
        self.list_again_process_done()
        return False

    def list_again_process_done(self):
        self.mainstack.set_visible_child_name("mainbox")
        self.listbox.show_all()
        self.listagain_btn.hide()  # the button doesn't need to appear after all files are listed
        return False  # 'GLib.idle_add' callback should not be called again
    # ----------------------


    # about screen
    def _on_aboutdialog(self, widget):
      self.about_dialog.run()
      self.about_dialog.hide()
      return


    def _on_destroy(self, widget):
        Gtk.main_quit()

app = pardusdocsearch()
Gtk.main()

