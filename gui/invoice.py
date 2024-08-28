import shutil
from copy import copy
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import xlwings
from openpyxl.utils import rows_from_range

from invoice_database import InvoiceDatabase
from invoice_s3 import InvoiceS3

EXCEL_INVOICE_FILENAME = "%B_{} %Y - ({})"

class InvoiceCloneRefusalError(Exception):
    """Raises an exception where the program attempts to clone via shutil.copy() but refuses to access.
    Separates from PermissionError."""
    pass

class CalendarData_Invoice_LinkedList:
    # Following header order based on student/teacher template as the formats are the same.
    def __init__(self, date, subject, person_name, rate, hour, amount, no_show=False):
        self._date = date
        self._subject = subject
        self._person_name = person_name
        self._rate = rate
        self._hour = hour
        self._amount = amount
        self._no_show = no_show

    def get_date(self):
        return self._date

    def get_subject(self):
        return self._subject

    def get_person_name(self):
        return self._person_name

    def get_rate(self):
        return self._rate

    def get_hour(self):
        return self._hour

    def get_amount(self):
        return self._amount

    def get_no_show(self):
        return self._no_show

"""
Function reference from: https://stackoverflow.com/questions/75390577/python-copy-entire-row-with-formatting
Author: moken
"""
def _copy_range(range_str, sheet, offset):
    """ Copy cell values and style to the new row using offset"""
    for row in rows_from_range(range_str):
        for cell in row:
            dst_cell = sheet[cell].offset(row=offset, column=0)
            src_cell = sheet[cell]

            ### Copy Cell value
            dst_cell.value = src_cell.value

            ### Copy Cell Styles
            dst_cell.font = copy(src_cell.font)
            dst_cell.alignment = copy(src_cell.alignment)
            dst_cell.border = copy(src_cell.border)
            dst_cell.fill = copy(src_cell.fill)

            dst_cell.number_format = src_cell.number_format

class PersonInvoice_LinkedList:
    def __init__(self, person_name: str, invoice: CalendarData_Invoice_LinkedList, invoice_id: str):
        self.person_name = person_name
        self.invoice = CalendarData_Inner_LinkedList(invoice)
        self.invoice_id = invoice_id
        self.next = None

class CalendarData_Inner_LinkedList:
    def __init__(self, invoice: CalendarData_Invoice_LinkedList):
        self.date = invoice.get_date()
        self.subject = invoice.get_subject()
        self.person_name = invoice.get_person_name()
        self.rate = invoice.get_rate()
        self.hour = invoice.get_hour()
        self.amount = invoice.get_amount()
        self.no_show = invoice.get_no_show()
        self.next = None

class Invoice:
    def __init__(self, schedule_date: datetime, invoice_database: InvoiceDatabase, invoice_s3: InvoiceS3):
        self._head = None

        self._to_override_all = False
        self._is_override_clicked = None

        self._today_date = datetime.now()
        self._schedule_date = schedule_date
        self._total_amount = 0

        self._invoice_database = invoice_database
        self._invoice_s3 = invoice_s3

    def __del__(self):
        while self._head:
            innerHead = self._head.invoice
            while innerHead:
                innerTail = innerHead.next
                del innerHead
                innerHead = innerTail
            tail = self._head.next
            del self._head
            self._head = tail

    def _create_unique_id(self, person_name: str, pay_period=False) -> str:
        schedule_date_str = self._schedule_date.strftime("%m%y")
        id_result = "".join([name[0] for name in person_name.split()])
        id_result += schedule_date_str
        if pay_period:
            id_result += "A" if self._schedule_date.day == 15 else "B"
        return id_result

    def store_calendar_invoice_data(self, person_name: str, invoice: CalendarData_Invoice_LinkedList):
        invoice_id = self._create_unique_id(person_name)
        if self._head == None:
            invoiceNode = PersonInvoice_LinkedList(person_name, invoice, invoice_id)
            self._head = invoiceNode
            return

        # Match the name from a given calendar data.
        temp = self._head
        while temp != None:
            if temp.person_name.title() == person_name.title():
                break
            elif temp.next == None:
                temp.next = PersonInvoice_LinkedList(person_name, invoice, invoice_id)
                return
            temp = temp.next

        invoiceTemp = temp.invoice
        invoiceNextTemp = invoiceTemp.next

        # Only one exists. Then it should replace 'next' with an actual node.
        if invoiceTemp.next == None:
            invoiceTemp.next = CalendarData_Inner_LinkedList(invoice)
            return

        # Check the boundaries between names with the current node and the next node.
        # Insert between if the parameter matches with the current node.
        # Ex: F -> F -> F -> T -> T -> R -> R
        # Parameter: T
        # F -> T: Doesn't match. T -> R: Matches!
        while invoiceTemp != None and invoiceNextTemp != None:
            if invoiceTemp.person_name.title() != invoiceNextTemp.person_name.title():
                if invoiceTemp.person_name.title() == invoice.get_person_name().title():
                    innerNode = CalendarData_Inner_LinkedList(invoice)
                    invoiceTemp.next = innerNode
                    innerNode.next = invoiceNextTemp
                    return

            invoiceTemp = invoiceTemp.next
            invoiceNextTemp = invoiceTemp.next

        # Insert at the end if it cannot find a way to insert in between.
        if invoiceNextTemp == None:
            invoiceTemp.next = CalendarData_Inner_LinkedList(invoice)

    def _create_file_destination(self, filepath: str, destination: str) -> None:
        local_path = Path(destination)
        local_path.parent.mkdir(exist_ok=True, parents=True)

        try:
            shutil.copy(filepath, destination)
        except shutil.SameFileError:
            pass
        except PermissionError:
            raise InvoiceCloneRefusalError("ERROR: Access denied while attempting to clone to {}".format(local_path))

    def _notify_file_existance_window(self, person_name: str, revised_date_filename: str):
        def _to_override():
            if override_all_option_var.get():
                self._to_override_all = True
            self._is_override_clicked = True
            file_exist_toplevel.quit()
            file_exist_toplevel.destroy()

        def _to_cancel():
            if override_all_option_var.get():
                self._to_override_all = True
            self._is_override_clicked = False
            file_exist_toplevel.quit()
            file_exist_toplevel.destroy()

        file_exist_toplevel = tk.Toplevel()
        file_exist_toplevel.title("File Exist Warning")
        file_exist_toplevel.resizable(False, False)
        label_msg = ttk.Label(file_exist_toplevel,
                              text="{}: This excel file exists for person {}! Override?\n"
                                   "It will not be calibrated if it's canceled!".format(
                                               revised_date_filename, person_name))
        label_msg.grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=10, pady=10)
        override_all_option_var = tk.BooleanVar()
        override_all_option_var.set(False)
        override_all_option = ttk.Checkbutton(file_exist_toplevel, text="Do this for all current items",
                                              variable=override_all_option_var)
        override_all_option.grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        option_1_button = ttk.Button(file_exist_toplevel, text="Override", command=_to_override)
        option_1_button.grid(row=2, column=1, sticky=tk.EW, padx=10, pady=10)
        option_2_button = ttk.Button(file_exist_toplevel, text="Cancel", command=_to_cancel)
        option_2_button.grid(row=2, column=2, sticky=tk.EW, padx=10, pady=10)

        file_exist_toplevel.mainloop()

    def _check_filepath_validation(self, person_name: str, filepath: str, destination: str, revised_date_filename: str) -> bool:
        # Check whether the file destination exists. If it doesn't, create one.
        # May not guarantee excel copy possibly due to permission error.
        try:
            if Path(destination).is_file():
                if not self._to_override_all:
                    self._notify_file_existance_window(person_name, revised_date_filename)

                if not self._is_override_clicked:
                    return False
            self._create_file_destination(filepath, destination)
        except InvoiceCloneRefusalError:
            if not messagebox.askyesno(title="Excel Currently Opened",
                                       message="{}: Unable to write excel file while the current sheet is opened! "
                                               "Close the application and try again? (UNSAVED CHANGES WILL BE LOST!)".format(
                                           revised_date_filename)):
                return False
            book = xlwings.Book(destination)
            book.close()
            self._create_file_destination(filepath, destination)
        except Exception as e:
            print(e)
            return False
        return True

    def write_invoice_to_excel(self) -> None:
        pass