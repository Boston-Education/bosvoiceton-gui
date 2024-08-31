import json
import re
import tkinter as tk
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
import calendar
import sys
import ast

import student_invoice
from invoice_database import InvoiceDatabase
from quickstart import BostonEDU_Google_Calendar
from invoice_file_listener import Invoice_File_Listener

VERSION = "beta-v0.1.0"

DEF_PADX = 10
DEF_PADY = 10

"""
Original source from: https://stackoverflow.com/questions/68198575/how-can-i-displaymy-console-output-in-tkinter
Credit: mnikley
"""
class PrintLogger(object):  # create file like object

    def __init__(self, textbox):  # pass reference to text widget
        self.textbox = textbox  # keep ref

    def write(self, text):
        self.textbox.configure(state="normal")  # make field editable
        self.textbox.insert("end", text)  # write text to textbox
        self.textbox.see("end")  # scroll to end
        self.textbox.configure(state="disabled")  # make field readonly

    def flush(self):  # needed for file like object
        pass

class Invoice_GUI:
    def __init__(self):
        self._auto_sync_updater_file()
        self._check_update()

        self._window = tk.Tk()
        self._window.title("BosVoiceTon | {}".format(VERSION))
        self._window.iconbitmap(self._window, r"image/icon.ico")
        self._window.resizable(False, False)
        self._window.geometry("680x570")
        self._tabControl = ttk.Notebook(self._window)

        self._tab1 = ttk.Frame(self._tabControl)
        self._tab2 = ttk.Frame(self._tabControl)
        self._tab3 = ttk.Frame(self._tabControl)
        self._tab4 = ttk.Frame(self._tabControl)
        self._tabControl.add(self._tab1, text="Generate Invoice")
        self._tabControl.add(self._tab2, text="Invoice Data")
        self._tabControl.add(self._tab3, text="Calendar Formatter")
        self._tabControl.add(self._tab4, text="About")
        self._tabControl.pack(expand=1, fill="both")

        #############################
        # [GENERATE INVOICE (TAB1)] #
        #############################

        self._console_label = ttk.Label(self._tab1, text="Console")
        self._console_label.grid(row=0, column=0, sticky=tk.W + tk.S, padx=DEF_PADX, pady=3)
        self._console_window = ScrolledText(self._tab1, state="disabled", font=("Arial", 10), width=91)
        self._console_window.grid(row=1, column=0, columnspan=5, sticky=tk.NSEW, padx=DEF_PADX, pady=3)
        # self._console_window = tk.Text(self._tab1, state="disabled")
        # self._console_window.grid(row=1, column=0, columnspan=5, sticky=tk.EW, padx=DEF_PADX, pady=3)
        # self._console_scrollbar = ttk.Scrollbar(self._tab1, orient="vertical", command=self._console_window.yview)
        # self._console_scrollbar.grid(row=1, column=4, sticky=tk.NS + tk.E, padx=DEF_PADX, pady=3)
        # self._console_window["yscrollcommand"] = self._console_scrollbar.set
        logger = PrintLogger(self._console_window)
        sys.stdout = logger
        sys.stderr = logger

        self._select_date_display = tk.Label(self._tab1, text="Select a date to begin generating invoice:")
        self._select_date_display.grid(row=2, columnspan=5, sticky=tk.W, padx=DEF_PADX)
        self._month_label = tk.Label(self._tab1, text="Month:")
        self._month_label.grid(row=3, column=0, sticky=tk.W, padx=DEF_PADX)

        self._month_combobox = ttk.Combobox(self._tab1, state="readonly")
        self._month_combobox['values'] = ('January','February','March',
                                            'April','May','June',
                                            'July','August','September',
                                            'October','November','December')
        self._month_combobox.current(int(datetime.now().strftime("%m")) - 1)
        # self._month_combobox.bind("<<ComboboxSelected>>", self._day_manipulator)
        self._month_combobox.grid(row=3, column=1, sticky=tk.W)

        self._year_label = tk.Label(self._tab1, text="Year:")
        self._year_label.grid(row=4, column=0, sticky=tk.W, padx=DEF_PADX)

        year = int(datetime.now().strftime("%Y"))
        self._year_combobox = ttk.Combobox(self._tab1, state="readonly")
        self._year_combobox['values'] = (year, year - 1)
        self._year_combobox.current(0)
        # self._year_combobox.bind("<<ComboboxSelected>>", self._day_manipulator)
        self._year_combobox.grid(row=4, column=1, sticky=tk.W)

        # self._day_manipulator(None)

        self._version_info = tk.Label(self._tab1, text="Build Version: {}".format(VERSION))
        self._version_info.grid(row=5, columnspan=5, sticky=tk.W + tk.S, padx=DEF_PADX, pady=DEF_PADY)

        # self._save_tuition_var = tk.BooleanVar()
        # self._save_tuition_var.set(False)
        # self._save_tuition_checkbutton = ttk.Checkbutton(self._tab1, text="Save Tuition", variable=self._save_tuition_var)
        # self._save_tuition_checkbutton.grid(row=3, column=4, sticky=tk.E, padx=DEF_PADX)
        self._startbutton = ttk.Button(self._tab1, text="Start", command=self._begin_invoice)
        self._startbutton.grid(row=4, column=4, sticky=tk.W + tk.E, padx=DEF_PADX, pady=DEF_PADY)

        self._connect_database()
        self._connect_s3_bucket()
        self._start_file_handler()

        #########################
        # [INVOICE DATA (TAB2)] #
        #########################

        self._data_text = tk.Label(self._tab2, text="Data Window:")
        self._data_text.grid(row=0, column=0, sticky=tk.W + tk.S, padx=DEF_PADX, pady=3)
        # self._data_window = ScrolledText(self._tab2, state="disabled", width=25)
        # self._data_window.grid(row=1, column=0, rowspan=4, sticky=tk.NSEW, padx=DEF_PADX, pady=3)

        self._data_window_treeview = ttk.Treeview(self._tab2, columns=("c1", "c2", "c3"), show="headings", height=18)
        self._data_window_treeview.column(0, stretch=tk.NO, width=30)
        self._data_window_treeview.heading(0, text="")
        self._data_window_treeview.column(1, stretch=tk.NO, width=115)
        self._data_window_treeview.heading(1, text="")
        self._data_window_treeview.column(2, stretch=tk.NO, width=70)
        self._data_window_treeview.heading(2, text="")
        self._data_window_treeview.grid(row=1, column=0, rowspan=4, sticky=tk.NSEW, padx=DEF_PADX, pady=3)

        self._student_rate_button = ttk.Button(self._tab2, text="Show Student/Teacher Code List", command=self._show_teacher_student_code)
        self._student_rate_button.grid(row=5, column=0, sticky=tk.EW, padx=DEF_PADX, pady=3)
        self._student_discount_button = ttk.Button(self._tab2, text="Show Discount", command=self._show_discount_amount)
        self._student_discount_button.grid(row=6, column=0, sticky=tk.EW, padx=DEF_PADX, pady=3)
        # self._student_tuition_button = ttk.Button(self._tab2, text="Show Tuition", command=self._show_tuition_amount)
        # self._student_tuition_button.grid(row=7, column=0, sticky=tk.EW, padx=DEF_PADX, pady=3)
        self._class_name_button = ttk.Button(self._tab2, text="Show Class", command=self._show_class_names)
        self._class_name_button.grid(row=7, column=0, sticky=tk.EW, padx=DEF_PADX, pady=3)
        self._clear_button = ttk.Button(self._tab2, text="Clear", command=self._clear_data_window)
        self._clear_button.grid(row=8, column=0, sticky=tk.EW, padx=DEF_PADX, pady=3)

        self._data_modify_text = tk.Label(self._tab2, text="Modify:")
        self._data_modify_text.grid(row=0, column=1, sticky=tk.W + tk.S, padx=DEF_PADX, pady=3)

        self._data_options_var = tk.IntVar()
        self._add_option = ttk.Radiobutton(self._tab2, text="Add",
                                           variable=self._data_options_var, value=1, command=self._data_location)
        self._add_option.grid(row=1, column=1, sticky=tk.N, padx=3, pady=3)
        self._update_option = ttk.Radiobutton(self._tab2, text="Update",
                                              variable=self._data_options_var, value=2, command=self._data_location)
        self._update_option.grid(row=1, column=1, padx=3, pady=3)
        self._delete_option = ttk.Radiobutton(self._tab2, text="Delete",
                                              variable=self._data_options_var, value=3, command=self._data_location)
        self._delete_option.grid(row=1, column=1, sticky=tk.S, padx=3, pady=3)

        self._data_name_label = ttk.Label(self._tab2, text="Student FULL Name:")
        self._data_name_label.grid(row=1, column=2, sticky=tk.E + tk.N, padx=3, pady=3)
        self._data_name_combobox = ttk.Combobox(self._tab2)
        self._data_name_combobox["values"] = [name[0] for name in sorted(self._database.get_all_student_name(), key=lambda x: x[0])]
        self._data_name_combobox.grid(row=1, column=3, sticky=tk.EW + tk.N, padx=3, pady=3)
        # self._data_name_entry = ttk.Entry(self._tab2)
        # self._data_name_entry.grid(row=1, column=3, sticky=tk.EW + tk.N, padx=3, pady=3)

        self._data_value_label = ttk.Label(self._tab2, text="Value:")
        self._data_value_label.grid(row=1, column=2, sticky=tk.E + tk.S, padx=3, pady=3)
        self._data_value_entry_var = tk.DoubleVar()
        self._data_value_entry = ttk.Entry(self._tab2, textvariable=self._data_value_entry_var)
        self._data_value_entry.bind("<FocusOut>", lambda _: self._auto_round_to_two_deci(self._data_value_entry_var))
        self._data_value_entry.grid(row=1, column=3, sticky=tk.EW + tk.S, padx=3, pady=3)

        self._data_location_label = ttk.Label(self._tab2, text="Database Location:")
        self._data_location_label.grid(row=1, column=2, sticky=tk.E, padx=3, pady=3)
        self._data_location_combobox = ttk.Combobox(self._tab2, state="readonly")
        self._data_location_combobox['values'] = ("Student", "Discount")
        self._data_location_combobox.bind("<<ComboboxSelected>>", self._data_location_event)
        self._data_location_combobox.grid(row=1, column=3, sticky=tk.EW, padx=3, pady=3)

        # self._data_tuition_as_calc_var = tk.BooleanVar()
        # self._data_tuition_as_calc_var.set(True)
        # self._data_tuition_as_calc = ttk.Checkbutton(self._tab2, text="Set Tuition as Calculation", variable=self._data_tuition_as_calc_var)
        # self._data_tuition_as_calc.grid(row=2, column=1, columnspan=5, sticky=tk.E + tk.N, padx=DEF_PADX, pady=DEF_PADY)

        self._data_sendrequest_button = ttk.Button(self._tab2, text="Send Request", command=self._process_database)
        self._data_sendrequest_button.grid(row=2, column=1, columnspan=4, sticky=tk.EW + tk.N, padx=3, pady=DEF_PADY)

        self._data_message_output = ttk.Label(self._tab2, text="")
        self._data_message_output.grid(row=2, column=1, columnspan=4, sticky=tk.W, padx=3)

        self._payment_label = ttk.Label(self._tab2, text="Payment:")
        self._payment_label.grid(row=2, column=1, sticky=tk.EW + tk.S, padx=3, pady=DEF_PADY)
        self._payment_name_label = ttk.Label(self._tab2, text="Student Name:")
        self._payment_name_label.grid(row=3, column=1, sticky=tk.E + tk.N, padx=3, pady=3)
        self._payment_name_combobox = ttk.Combobox(self._tab2)
        self._payment_name_combobox["values"] = [name[0] for name in sorted(self._database.get_all_student_name(), key=lambda x: x[0])]
        self._payment_name_combobox.grid(row=3, column=2, sticky=tk.EW + tk.N, padx=3, pady=3)

        # self._payment_date_label = ttk.Label(self._tab2, text="Date of Payment:")
        # self._payment_date_label.grid(row=3, column=1, sticky=tk.E + tk.S, padx=3, pady=3)
        # self._payment_date_entry = ttk.Entry(self._tab2)
        # self._payment_date_entry.insert(tk.END, datetime.now().strftime("%B %d, %Y"))
        # self._payment_date_entry.configure(state="disabled")
        # self._payment_date_entry.grid(row=3, column=2, sticky=tk.EW + tk.S, padx=3, pady=3)

        self._payment_amount_label = ttk.Label(self._tab2, text="Amount:")
        self._payment_amount_label.grid(row=3, column=1, sticky=tk.E, padx=3, pady=3)
        self._payment_amount_entry_var = tk.DoubleVar()
        self._payment_amount_entry = ttk.Entry(self._tab2, textvariable=self._payment_amount_entry_var)
        self._payment_amount_entry.bind("<FocusOut>", lambda _: self._auto_round_to_two_deci(self._payment_amount_entry_var))
        self._payment_amount_entry.grid(row=3, column=2, sticky=tk.EW, padx=3, pady=3)

        self._payment_type_label = ttk.Label(self._tab2, text="Payment Type:")
        self._payment_type_label.grid(row=3, column=1, sticky=tk.E + tk.S, padx=3, pady=3)
        self._payment_type_combobox = ttk.Combobox(self._tab2)
        self._payment_type_combobox["values"] = ("Cash", "Checks", "Venmo", "Zelle", "PayPal")
        self._payment_type_combobox.grid(row=3, column=2, sticky=tk.EW + tk.S, padx=3, pady=3)

        self._payment_apply_button = ttk.Button(self._tab2, text="Make Payment", command=self._update_payment)
        self._payment_apply_button.grid(row=4, column=1, columnspan=4, sticky=tk.EW + tk.N, padx=3, pady=DEF_PADY)

        self._payment_message_label = ttk.Label(self._tab2, text="")
        self._payment_message_label.grid(row=4, column=1, rowspan=2, columnspan=4, sticky=tk.W, padx=3)

        ###############################
        # [CALENDAR FORMATTER (TAB3)] #
        ###############################

        self._preview_text = ttk.Label(self._tab3, text="Preview:")
        self._preview_text.grid(row=0, column=0, padx=DEF_PADX, pady=DEF_PADY)

        self._preview = tk.StringVar()
        self._preview_textbox = tk.Entry(self._tab3, textvariable=self._preview)
        self._preview_textbox.config(state="readonly")
        self._preview_textbox.grid(row=0, column=1, columnspan=7, sticky=tk.W + tk.E, padx=DEF_PADX, pady=DEF_PADY)

        self._hor_separator = ttk.Separator(self._tab3, orient="horizontal")
        self._hor_separator.grid(row=1, columnspan=8, sticky=tk.EW, padx=DEF_PADX, pady=DEF_PADY)

        self._comma_description = ttk.Label(self._tab3, text="TIP: Separate the names with comma to see the full list again.")
        self._comma_description.grid(row=2, columnspan=8, sticky=tk.EW + tk.S, padx=DEF_PADX, pady=DEF_PADY)

        self._cxl = tk.BooleanVar()
        self._cxl.set(False)
        self._cxl_checkbox = ttk.Checkbutton(self._tab3, text="CXL", variable=self._cxl, command=self._update_preview)
        self._cxl_checkbox.grid(row=3, column=7, sticky=tk.W + tk.E, padx=DEF_PADX)

        self._noshow = tk.BooleanVar()
        self._noshow.set(False)
        self._noshow_checkbox = ttk.Checkbutton(self._tab3, text="No Show", variable=self._noshow, command=self._update_preview)
        self._noshow_checkbox.grid(row=5, column=7, sticky=tk.W + tk.E, padx=DEF_PADX, pady=DEF_PADY)

        self._teacher_name_text = ttk.Label(self._tab3, text="Teacher Name:")
        self._teacher_name_text.grid(row=3, column=0, padx=DEF_PADX)
        self._teacher_name_entry = ttk.Entry(self._tab3)
        self._teacher_name_entry.bind("<KeyRelease>", self._update_teacher_listbox)
        self._teacher_name_entry.grid(row=3, column=1, sticky=tk.W + tk.E, padx=DEF_PADX)

        self._teacher_name_listbox = tk.Listbox(self._tab3, selectmode="single", exportselection=0)

        for teacher in sorted(self._database.get_all_teacher_name(), key=lambda x: x[0]):
            self._teacher_name_listbox.insert(tk.END, teacher[0])

        self._teacher_name_listbox.bind("<<ListboxSelect>>", self._update_teacher_entry)
        self._teacher_name_listbox.grid(row=4, column=1, sticky=tk.NSEW, padx=DEF_PADX)

        self._student_name_text = ttk.Label(self._tab3, text="Student Name:")
        self._student_name_text.grid(row=3, column=2, padx=DEF_PADX)
        self._student_name_entry = ttk.Entry(self._tab3)
        self._student_name_entry.bind("<KeyRelease>", self._update_student_listbox)
        self._student_name_entry.grid(row=3, column=3, columnspan=4, sticky=tk.W + tk.E, padx=DEF_PADX)
        
        self._student_name_listbox = tk.Listbox(self._tab3, selectmode="single", exportselection=0)

        for student in sorted(self._database.get_all_student_name(), key=lambda x: x[0]):
            self._student_name_listbox.insert(tk.END, student[0])

        self._student_name_listbox.bind("<<ListboxSelect>>", self._update_student_entry)
        self._student_name_listbox.grid(row=4, column=3, columnspan=4, sticky=tk.NSEW, padx=DEF_PADX)
        
        self._class_name_text = ttk.Label(self._tab3, text="Class Name:")
        self._class_name_text.grid(row=5, column=0, padx=DEF_PADX, pady=DEF_PADY)
        self._class_name_combobox = ttk.Combobox(self._tab3)
        self._class_name_combobox["values"] = [classname[0] for classname in sorted(self._database.get_all_class_name(), key=lambda x: x[0])]
        self._class_name_combobox.bind("<<ComboboxSelected>>", self._update_preview_event)
        self._class_name_combobox.bind("<KeyRelease>", self._update_preview_event)
        self._class_name_combobox.grid(row=5, column=1, sticky=tk.W + tk.E, padx=DEF_PADX, pady=DEF_PADY)

        self._codename_text = ttk.Label(self._tab3, text="Code:")
        self._codename_text.grid(row=5, column=2, padx=DEF_PADX, pady=DEF_PADY)

        self._teacher_code_text = ttk.Label(self._tab3, text="T")
        self._teacher_code_text.grid(row=5, column=3, sticky=tk.E, padx=DEF_PADX, pady=2)

        self._t_asterisk = tk.BooleanVar()
        self._t_asterisk.set(False)
        self._teacher_asterisk_checkbox = ttk.Checkbutton(self._tab3, text="*", variable=self._t_asterisk, command=self._update_preview)
        self._teacher_asterisk_checkbox.grid(row=6, column=4, sticky=tk.W, padx=DEF_PADX, pady=2)
        self._teacher_code_combobox = ttk.Combobox(self._tab3, width=3)
        self._teacher_code_combobox["values"] = [teachercode[0] for teachercode in self._database.get_teacher_code()]
        self._teacher_code_combobox.bind("<<ComboboxSelected>>", self._update_preview_event)
        self._teacher_code_combobox.bind("<KeyRelease>", self._update_preview_event)
        self._teacher_code_combobox.grid(row=5, column=4, sticky=tk.W, padx=DEF_PADX, pady=2)

        self._student_code_text = ttk.Label(self._tab3, text="S")
        self._student_code_text.grid(row=5, column=5, sticky=tk.E, padx=DEF_PADX, pady=2)

        self._s_asterisk = tk.BooleanVar()
        self._s_asterisk.set(False)
        self._student_asterisk_checkbox = ttk.Checkbutton(self._tab3, text="*", variable=self._s_asterisk, command=self._update_preview)
        self._student_asterisk_checkbox.grid(row=6, column=6, sticky=tk.W, padx=DEF_PADX, pady=2)
        self._student_code_combobox = ttk.Combobox(self._tab3, width=3)
        self._student_code_combobox["values"] = [studentcode[0] for studentcode in self._database.get_student_code()]
        self._student_code_combobox.bind("<<ComboboxSelected>>", self._update_preview_event)
        self._student_code_combobox.bind("<KeyRelease>", self._update_preview_event)
        self._student_code_combobox.grid(row=5, column=6, sticky=tk.W, padx=DEF_PADX, pady=2)

        self._online = tk.BooleanVar()
        self._online.set(False)
        self._online_checkbox = ttk.Checkbutton(self._tab3, text="Online", variable=self._online, command=self._update_preview)
        self._online_checkbox.grid(row=4, column=7, sticky=tk.W + tk.E, padx=DEF_PADX, pady=DEF_PADY)

        ##################
        # [ABOUT (TAB4)] #
        ##################

        self._boston_logo_image = tk.PhotoImage(file="image/bostonedu_logo.png")
        self._boston_logo_image_label = ttk.Label(self._tab4, image=self._boston_logo_image)
        self._boston_logo_image_label.grid(row=0, column=0, sticky=tk.W, padx=DEF_PADX, pady=DEF_PADY)

        self._author_label = ttk.Label(self._tab4, text="Written and developed by:\n\nRuleon Ki Lee")
        self._author_label.grid(row=0, column=1, sticky=tk.W, padx=DEF_PADX, pady=DEF_PADY)

        self._about_description_label = ttk.Label(self._tab4, text="An invoice program designed to provide quality-of-life features\n"
                                                                   "to make easily and consistently. This aims to auto-generate\n"
                                                                   "invoice Excel sheets based on Google Calendar data.")
        self._about_description_label.grid(row=1, column=0, sticky=tk.W, padx=DEF_PADX, pady=DEF_PADY)
        self._about_copyright_disclaimer_label = ttk.Label(self._tab4, text="Copyright © 2023-2024 Boston Education. All Rights Reserved.")
        self._about_copyright_disclaimer_label.grid(row=2, column=0, sticky=tk.W, padx=DEF_PADX, pady=DEF_PADY)

        self._window.protocol("WM_DELETE_WINDOW", self._quit_application)

    def _check_update(self) -> None:
        try:
            updater_url = "https://raw.githubusercontent.com/RueLee/BosVoiceTon/main/updater.json"
            updater_url_request = urllib.request.Request(updater_url)
            updater_url_response = urllib.request.urlopen(updater_url_request)

            updater_data = updater_url_response.read()
            updater_data_json = json.loads(updater_data.decode("utf-8"))
            updater_url_response.close()

            latest_version = updater_data_json["latest_version"]
            if VERSION != latest_version:
                if not messagebox.askyesno(title="Update Available!", message="A new update is available! Would you like to open and download the latest version?\n\n"
                                                                              "Your Version: {}\n"
                                                                              "Latest Version: {}".format(VERSION, latest_version)):
                    return

                webbrowser.open_new_tab("https://github.com/RueLee/BostonEdu_Invoice_2023/releases/tag/{}".format(latest_version))
                sys.exit(0)
        except urllib.error.HTTPError as httpError:
            messagebox.showerror(title="WEBSITE ERROR", message="Got an HTTP code of {} when attempting to check for updates!".format(httpError.getcode()))
        except urllib.error.URLError:
            messagebox.showerror(title="NETWORK ERROR", message="Unable to establish connection to check for updates in the repository!")

    def _auto_sync_updater_file(self) -> None:
        """For local repository only!"""
        try:
            current_path = Path().cwd()
            parent_path = current_path.parent
            updater_path = parent_path / "updater.json"

            with open(updater_path, "r", encoding="utf-8") as inpath:
                updater_json = json.load(inpath)
                inpath.close()

            updater_json["latest_version"] = VERSION

            with open(updater_path, "w", encoding="utf-8") as outpath:
                json.dump(updater_json, outpath, indent=4)
                outpath.close()
        except FileNotFoundError:
            pass

    def _connect_database(self) -> None:
        try:
            self._database = InvoiceDatabase()
            print("Successfully established connection to database!")
        except:
            messagebox.showerror(title="MYSQL Connection Failed!", message="Unable to connect to the database!\nVerify that the information is correct and try again.")
            sys.exit(0)

    def _connect_s3_bucket(self) -> None:
        # try:
        #     # TODO: Test offline capabilities
        #     self._s3_bucket = InvoiceS3()
        #     print("Successfully established connection to s3 bucket (file service)!")
        #
        #     self._s3_bucket.verify_file_integrity()
        #     print("Your file is now up to date with remote file storage!")
        # except Exception as e:
        #     if not messagebox.askquestion(title="S3 Connection Failed!", message="Unable to connect to remote file storage!\nWould you like to download offline instead?\n"
        #                                                                 "(NOT RECOMMENDED)"):
        #         sys.exit(0)
        self._s3_bucket = None

    def _start_file_handler(self):
        try:
            self._ifl = Invoice_File_Listener()
        except FileNotFoundError:
            print(
                "ERROR: System is unable to watch output folders for any modifications! Please try generating invoice and relaunch the application!")
            self._ifl = None

    def _process_database(self) -> None:
        student_name = self._data_name_combobox.get()

        if len(student_name) == 0:
            self._data_message_output.configure(
                text="Please input the student name entry!")
            return

        try:
            amount = self._data_value_entry_var.get()
        except tk.TclError:
            self._data_message_output.configure(text="ERROR: Only digits are supported for the 'Value' entry. Please try another input!")
            return

        data_option_mode = self._data_options_var.get()
        name_checker = self._database.find_student_info(student_name)
        if name_checker == None and data_option_mode != 1:
            self._data_message_output.configure(
                text="ERROR: Cannot find a student named {}! Please try another input!".format(student_name))
            return

        data_combo = self._data_location_combobox.get()

        if data_option_mode == 1:       # Add
            if data_combo == "Student":
                data_status = self._database.create_student_info(student_name)
            elif data_combo == "Discount":
                data_status = self._database.create_discount_amount(student_name, amount)
            else:
                self._data_message_output.configure(
                    text="ERROR: Please specify the database location!")
                return
        elif data_option_mode == 2:     # Update
            if data_combo == "Discount":
                data_status = self._database.set_discount_amount(student_name, amount)
            else:
                self._data_message_output.configure(
                    text="ERROR: Please specify the database location!")
                return
        elif data_option_mode == 3:       # Delete
            if data_combo == "Student":
                if not messagebox.askyesno(title="Deletion Warning", message="Deleting student name will also delete any data companion such as discount.\n\n"
                                                                             "Do you wish to continue? THIS ACTION CANNOT BE UNDONE!", icon="warning"):
                    return

                data_status = self._database.delete_student_info(student_name)
            elif data_combo == "Discount":
                data_status = self._database.delete_discount_amount(student_name)
            else:
                self._data_message_output.configure(
                    text="ERROR: Please specify the database location!")
                return
        else:
            self._data_message_output.configure(
                text="Option button not selected (Add/Update/Delete)!\nClick one of the following to proceed!")
            return
        if data_status:
            self._data_name_combobox.delete(0, tk.END)
            self._data_name_combobox["values"] = [name[0] for name in sorted(self._database.get_all_student_name(), key=lambda x: x[0])]
            self._data_message_output.configure(text="Successfully executed prompt!")
        else:
            self._data_message_output.configure(text="ERROR: Database cannot find the input specified or it already exists!")

    # def _day_manipulator(self, event) -> None:
    #     day_value = 15
    #     self._day_intvar = tk.IntVar()
    #     day_15_16 = ttk.Radiobutton(self._tab1, text="1-15", variable=self._day_intvar, value=day_value)
    #     day_15_16.grid(row=3, column=2, sticky=tk.W)
    #
    #     day_last_value = calendar.monthrange(int(self._year_combobox.get()), self._month_combobox['values'].index(self._month_combobox.get()) + 1)[1]
    #     day_last = ttk.Radiobutton(self._tab1, text="16-{}".format(day_last_value), variable=self._day_intvar, value=day_last_value)
    #     day_last.grid(row=4, column=2, sticky=tk.W)

    def _begin_invoice(self) -> None:
        month = self._month_combobox['values'].index(self._month_combobox.get()) + 1
        year = int(self._year_combobox.get())

        if not messagebox.askyesno(title="Confirm Proceeding", message="Generate invoice for {} {}?".format(self._month_combobox.get(), year)):
            return

        datetime_month_prompt = datetime(year, month, 1).month
        datetime_month_today = datetime.now().month
        if datetime_month_prompt > datetime_month_today:
            if not messagebox.askyesno(title="Future Date Notice", message="The month you selected has not reached from our current time. Continue anyway?"):
                return

        print("Date set to {} {}! Initializing data from Google Calendar!".format(self._month_combobox.get(), self._year_combobox.get()))
        print(f"{"Waiting for authorization...":-^80}")

        bost_google_cal = BostonEDU_Google_Calendar(self._database, self._s3_bucket)
        bost_google_cal.read_calendar_info(month, 1, 15, year, True)
        bost_google_cal.read_calendar_info(month, 16, calendar.monthrange(year, month)[1], year, True)
        bost_google_cal.read_calendar_info(month, 1, calendar.monthrange(year, month)[1], year, False)
        self._update_data_display()

    def _update_data_display(self):
        self._data_name_combobox["values"] = [name[0] for name in sorted(self._database.get_all_student_name(), key=lambda x: x[0])]
        self._update_student_listbox()
        self._update_teacher_listbox()
        self._class_name_combobox["values"] = [classname[0] for classname in sorted(self._database.get_all_class_name(), key=lambda x: x[0])]

    def _clear_data_window(self):
        for item in self._data_window_treeview.get_children():
            self._data_window_treeview.delete(item)

        self._data_window_treeview.column(0, stretch=tk.NO, width=30)
        self._data_window_treeview.heading(0, text="")
        self._data_window_treeview.column(1, stretch=tk.NO, width=115)
        self._data_window_treeview.heading(1, text="")
        self._data_window_treeview.column(2, stretch=tk.NO, width=70)
        self._data_window_treeview.heading(2, text="")

    def _show_teacher_student_code(self) -> None:
        self._clear_data_window()

        self._data_window_treeview.column(0, stretch=tk.NO, width=100)
        self._data_window_treeview.heading(0, text="Code", command=lambda: self._sort_treeview(self._data_window_treeview, "c1", False))
        self._data_window_treeview.column(1, stretch=tk.NO, width=115)
        self._data_window_treeview.heading(1, text="Rate", command=lambda: self._sort_treeview(self._data_window_treeview, "c2", False))
        self._data_window_treeview.column(2, stretch=tk.NO, width=0)
        self._data_window_treeview.heading(2, text="")

        tea_exec_result = self._database.get_teacher_code()
        stu_exec_result = self._database.get_student_code()

        for i in tea_exec_result:
            self._data_window_treeview.insert("", "end", values=tuple(i))
        self._data_window_treeview.insert("", "end", values=("", "", ""))
        for i in stu_exec_result:
            self._data_window_treeview.insert("", "end", values=tuple(i))

    def _show_discount_amount(self) -> None:
        self._clear_data_window()

        self._data_window_treeview.column(0, stretch=tk.NO, width=30)
        self._data_window_treeview.heading(0, text="ID", command=lambda: self._sort_treeview(self._data_window_treeview, "c1", False))
        self._data_window_treeview.column(1, stretch=tk.NO, width=115)
        self._data_window_treeview.heading(1, text="Student Name", command=lambda: self._sort_treeview(self._data_window_treeview, "c2", False))
        self._data_window_treeview.column(2, stretch=tk.NO, width=70)
        self._data_window_treeview.heading(2, text="Discount", command=lambda: self._sort_treeview(self._data_window_treeview, "c3", False))

        exec_result = self._database.get_all_discount_amount()
        for i in exec_result:
            self._data_window_treeview.insert("", "end", values=tuple(i))

    def _show_class_names(self) -> None:
        self._clear_data_window()

        self._data_window_treeview.column(0, stretch=tk.NO, width=30)
        self._data_window_treeview.heading(0, text="AP?", command=lambda: self._sort_treeview(self._data_window_treeview, "c1", False))
        self._data_window_treeview.column(1, stretch=tk.NO, width=30)
        self._data_window_treeview.heading(1, text="H?", command=lambda: self._sort_treeview(self._data_window_treeview, "c2", False))
        self._data_window_treeview.column(2, stretch=tk.NO, width=155)
        self._data_window_treeview.heading(2, text="Class Name", command=lambda: self._sort_treeview(self._data_window_treeview, "c3", False))

        exec_result = self._database.get_all_class_row()
        for i in exec_result:
            self._data_window_treeview.insert("", "end", values=tuple(i))

    """
    Function obtained from:
    https://www.w3resource.com/python-exercises/tkinter/python-tkinter-widgets-exercise-18.php
    """
    # Function to sort the Treeview by column
    def _sort_treeview(self, tree: ttk.Treeview, col: str, descending: bool):
        data = [(tree.set(item, col), item) for item in tree.get_children('')]
        try:
            data.sort(key=lambda x: ast.literal_eval(x[0]), reverse=descending)
        except SyntaxError:
            data.sort(reverse=descending)
        except ValueError:
            data.sort(reverse=descending)
        for index, (val, item) in enumerate(data):
            tree.move(item, '', index)
        tree.heading(col, command=lambda: self._sort_treeview(tree, col, not descending))

    def _data_location_event(self, event):
        self._data_value_entry.configure(state="normal")
        data_combo = self._data_location_combobox.get()
        if data_combo == "Student":
            self._data_value_entry.configure(state="disabled")

    def _data_location(self):
        self._data_location_combobox.set("")

        data_option_mode = self._data_options_var.get()
        if data_option_mode == 1:
            self._data_location_combobox['values'] = ("Student", "Discount")
        elif data_option_mode == 2:
            self._data_location_combobox['values'] = "Discount"
        elif data_option_mode == 3:
            self._data_location_combobox['values'] = ("Student", "Discount")

    def _update_payment(self):
        payment_amount = self._payment_amount_entry_var.get()
        if payment_amount <= 0:
            self._payment_message_label.configure(text="Please enter an amount greater than 0.")
            return

        payment_type = self._payment_type_combobox.get()
        if payment_type not in self._payment_type_combobox["values"]:
            self._payment_message_label.configure(text="ERROR: Invalid payment type!")
            return

        student = self._database.find_student_info(self._payment_name_combobox.get())
        if student == None:
            self._payment_message_label.configure(text="ERROR: No student exists in our database!")
            return

        try:
            student_invoice.update_tuition_amount(student[0].title(), payment_amount, payment_type)
            self._payment_message_label.configure(text="Successfully executed prompt!")
            self._payment_name_combobox.delete(0, tk.END)
        except FileNotFoundError:
            self._payment_message_label.configure(text="ERROR: Unable to locate file when attempting to access!\n"
                                                       "Make sure the sheet exists in this student name and try again!")
        except IndexError:
            self._payment_message_label.configure(text="ERROR: Found empty folder in this student name!")
        except PermissionError:
            self._payment_message_label.configure(text="ERROR: Permission denied! Close the current sheet application and try again!")

    def _update_teacher_listbox(self, event=None):
        value = re.split(r",(?:\s*)", self._teacher_name_entry.get())[-1]
        teacher_list = sorted(self._database.get_all_teacher_name(), key=lambda x: x[0][0])
        if value == "":
            matched_data = [teacher[0] for teacher in teacher_list]
        else:
            matched_data = [teacher[0] for teacher in teacher_list if value.title() in teacher[0].title()]

        self._teacher_name_listbox.delete(0, tk.END)
        for value in matched_data:
            self._teacher_name_listbox.insert(tk.END, value)

        self._update_preview()

    def _update_teacher_entry(self, event):
        selected_value = re.split(r",(?:\s*)", self._teacher_name_entry.get())
        selected_value.pop(-1)
        selected_value.extend([self._teacher_name_listbox.get(idx) for idx in self._teacher_name_listbox.curselection()])
        self._teacher_name_entry.delete(0, tk.END)
        self._teacher_name_entry.insert(tk.END, ", ".join(value for value in selected_value))
        self._update_preview()
        
    def _update_student_listbox(self, event=None):
        value = re.split(r",(?:\s*)", self._student_name_entry.get())[-1]
        student_list = sorted(self._database.get_all_student_name(), key=lambda x: x[0][0])
        if value == "":
            matched_data = [student[0] for student in student_list]
        else:
            matched_data = [student[0] for student in student_list if value.title() in student[0].title()]

        self._student_name_listbox.delete(0, tk.END)
        for value in matched_data:
            self._student_name_listbox.insert(tk.END, value)

        self._update_preview()

    def _update_student_entry(self, event):
        selected_value = re.split(r",(?:\s*)", self._student_name_entry.get())
        selected_value.pop(-1)
        selected_value.extend([self._student_name_listbox.get(idx) for idx in self._student_name_listbox.curselection()])
        self._student_name_entry.delete(0, tk.END)
        self._student_name_entry.insert(tk.END, ", ".join(value for value in selected_value))
        self._update_preview()

    def _update_preview(self) -> None:
        self._cxl_checkbox.configure(state="normal")
        self._noshow_checkbox.configure(state="normal")
        if self._cxl.get():
            first_str = "CXL - "
            self._noshow_checkbox.configure(state="disabled")
        elif self._noshow.get():
            first_str = "NS - "
            self._cxl_checkbox.configure(state="disabled")
        else:
            first_str = ""

        self._preview_string = "{}{} - {} - {} - {}{}{}{} - {}".format(first_str,
                                                            self._teacher_name_entry.get().title(),
                                                            self._student_name_entry.get().title(),
                                                            self._class_name_combobox.get(),
                                                            self._teacher_code_combobox.get(),
                                                                       "*" if self._t_asterisk.get() else "",
                                                            self._student_code_combobox.get(),
                                                                       "*" if self._s_asterisk.get() else "",
                                                            "Online" if self._online.get() else "In Person")
        self._preview.set(self._preview_string)

    def _update_preview_event(self, event) -> None:
        self._update_preview()

    def _auto_round_to_two_deci(self, float_var: tk.DoubleVar):
        float_var.set(round(float_var.get(), 2))

    def run(self) -> None:
        self._window.mainloop()

    def _quit_application(self) -> None:
        if self._ifl is None or self._s3_bucket is None:
            self._window.destroy()
            return

        ifl_file_list = list(self._ifl.get_file_event_list())
        ifl_str_res = "\n".join(file_msg for file_msg in ifl_file_list)
        if len(ifl_file_list) > 0:
            file_change_res = messagebox.askyesnocancel(title="Detected File Change(s)", message="A system has detected a file change on your local machine:\n\n{}\n\n"
                                                                         "Save and upload to service?".format(ifl_str_res))
            if file_change_res:
                for filename in ifl_file_list:
                    try:
                        self._s3_bucket.upload_file(filename, filename)
                    except FileNotFoundError:
                        pass
            elif file_change_res is None:
                return

        self._database.__del__()
        self._ifl.__del__()
        self._window.destroy()
