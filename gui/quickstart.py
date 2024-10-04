"""
Original source from: https://developers.google.com/calendar/api/quickstart/python
Date accessed: Dec. 21, 2023
"""
import re
from datetime import datetime
import pytz

import google.auth.exceptions
import os.path
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from invoice_s3 import InvoiceS3
from invoice_database import InvoiceDatabase
from invoice import Invoice, CalendarData_Invoice_LinkedList
from calendar_title import LineItem
from hourly_rates_offline import BostonEdu_HourlyRates_Offline
from student_invoice import StudentInvoice
from teacher_invoice import TeacherInvoice

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

RE_CXL = r"(?:\s*)\((?:\s*)(C|c)(X|x)(L|l)(?:\s*)\)(?:\s*)"
RE_CXL_COMPILE = re.compile(RE_CXL)
RE_NOSHOW = r"(?:\s*)\((?:\s*)(N|n)(S|s)(?:\s*)\)(?:\s*)"
RE_PARENTHESIS = r"(?:\s*)\((?:\s*)(\S|\s)*(?:\s*)\)(?:\s*)"

class BostonEDU_Google_Calendar:
    def __init__(self, invoice_database: InvoiceDatabase, invoice_s3: InvoiceS3):
        self._creds = None
        self._invoice_database = invoice_database
        self._invoice_s3 = invoice_s3
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            self._creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                try:
                    self._creds.refresh(Request())
                except google.auth.exceptions.RefreshError as err:
                    print(err)
                    print("\n")
                    print("Regenerating new token...")
                    Path(r"token.json").unlink()
                    self.__init__(invoice_database, invoice_s3)
                    return
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                self._creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(self._creds.to_json())

            print("Connection to Google Calendar has been successful!")

    def read_calendar_info(self, month: int, dayMin: int, dayMax: int, year: int, check_teacher: bool):
        try:
            # Call the Calendar API
            service = build("calendar", "v3", credentials=self._creds)

            self._timeMax = datetime(year, month, dayMax, tzinfo=pytz.timezone("America/Los_Angeles"))
            timeMax_fixed = self._timeMax.replace(hour=23, minute=59, second=59).isoformat()

            self._timeMin = datetime(year, month, dayMin, tzinfo=pytz.timezone("America/Los_Angeles"))
            print("Retrieving information ranged from {} to {}!".format(self._timeMin, timeMax_fixed))
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMax=timeMax_fixed,
                    timeMin=self._timeMin.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=2500,
                )
                .execute()
            )
            events = events_result.get("items", [])
            print("Number of events in this range: {}".format(len(events)))

            if not events:
                print("No upcoming events found.")
                return

            if check_teacher:
                self._process_teacher_invoice(events)
            else:
                self._process_student_invoice(events)

            print(f"{"Done writing invoice data!":-^80}")
        except HttpError as error:
            print(f"An error occurred: {error}")

    def check_cxl_pattern(self, lineitem: LineItem) -> bool:
        if lineitem.get_canceled_status():
            return True

        cxl_counter = 0
        student_list = lineitem.get_student_names()
        for student in student_list:
            if re.search(RE_CXL, student):
                cxl_counter += 1

        return cxl_counter >= len(student_list)

    def check_noshow_pattern(self, lineitem: LineItem) -> bool:
        if lineitem.get_no_show_status():
            return True

        ns_counter = 0
        student_list = lineitem.get_student_names()
        for student in student_list:
            if re.search(RE_NOSHOW, student):
                ns_counter += 1

        return ns_counter >= len(student_list)

    def _check_and_obtain_calendar_variables(self, event) -> LineItem | None:
        try:
            lineitem = LineItem(event["summary"])
        except IndexError:
            print("ERROR: Invalid invoice calendar format: {}! Skipping...".format(event["summary"]))
            return None
        except Exception as e:
            print(e)
            return None

        if re.search(RE_PARENTHESIS, lineitem.get_teacher_name()):
            print("WARNING: Parenthesis found in teacher name: {}! Ignoring flags...".format(event["summary"]))

        self._invoice_database.create_course_info(lineitem.get_class_name())
        return lineitem

    def _process_student_invoice(self, events) -> None:
        student_invoice = StudentInvoice(self._timeMin, self._timeMax, self._invoice_database, self._invoice_s3)

        # for event in events:
        #     print(event["summary"], event["start"].get("dateTime"))

        for event in events:
            lineitem = self._check_and_obtain_calendar_variables(event)
            if lineitem is None:
                continue

            delta = 0

            is_cxl_valid = self.check_cxl_pattern(lineitem)
            is_noshow_valid = self.check_noshow_pattern(lineitem)
            if not is_cxl_valid:
                delta = datetime.fromisoformat(event["end"].get("dateTime")) - datetime.fromisoformat(
                    event["start"].get("dateTime"))
                delta = delta.total_seconds() / 3600
                # if is_noshow_valid:
                #     delta /= 2

            schedule_date = datetime.strptime(event["start"].get("dateTime")[:10], "%Y-%m-%d")

            code_name = lineitem.get_code_names()

            stu_base_rate = int(re.findall(r"S([0-9a-fA-F])+$", code_name)[0], 16)
            stu_base_rate = abs(stu_base_rate)  # Prevent negative numbers from entering invoice.

            for student in lineitem.get_student_names():
                re_fixed_student = re.sub(RE_PARENTHESIS, "", student)  # Remove parenthesis adjacent to student name
                self._invoice_database.create_student_info(re_fixed_student)

                is_cxl_tagged = re.search(RE_CXL, student)
                student_date = schedule_date.strftime("%m/%d/%Y")
                student_class = lineitem.get_class_name()
                student_teacher = lineitem.get_teacher_name()
                student_rate = 0 if is_cxl_tagged else stu_base_rate
                student_hour = 0 if is_cxl_tagged else delta
                student_amount = 0 if is_cxl_tagged else stu_base_rate * delta
                student_no_show = is_noshow_valid or re.search(RE_NOSHOW, student)

                stu_invoice = CalendarData_Invoice_LinkedList(student_date, student_class, student_teacher,
                                      student_rate, student_hour, student_amount, student_no_show)
                student_invoice.store_calendar_invoice_data(re_fixed_student, stu_invoice)

        student_invoice.write_invoice_to_excel()
        student_invoice.__del__()

        print(r"Your file has been saved to: {}\base_generated".format(Path().absolute()))

    def _process_teacher_invoice(self, events) -> None:
        teacher_invoice = TeacherInvoice(self._timeMin, self._timeMax, self._invoice_database, self._invoice_s3)

        for event in events:
            lineitem = self._check_and_obtain_calendar_variables(event)
            if lineitem is None:
                continue

            delta = 0

            re_fixed_teacher = re.sub(RE_PARENTHESIS, "", lineitem.get_teacher_name())
            # Any schedule that has CXL marked or all students marked with "(CXL)" adjacent
            # will be skipped calculating delta and storing teacher invoice.
            is_cxl_valid = self.check_cxl_pattern(lineitem)
            is_noshow_valid = self.check_noshow_pattern(lineitem)
            if not is_cxl_valid:
                delta = datetime.fromisoformat(event["end"].get("dateTime")) - datetime.fromisoformat(
                    event["start"].get("dateTime"))
                delta = delta.total_seconds() / 3600
                if is_noshow_valid:
                    delta /= 2

                excluded_cxl_list = list(filter(lambda x: not RE_CXL_COMPILE.search(x), lineitem.get_student_names()))

                schedule_date = datetime.strptime(event["start"].get("dateTime")[:10], "%Y-%m-%d")

                code_name = lineitem.get_code_names()

                tea_base_rate = int(re.findall(r"^T([0-9a-fA-F])+", code_name)[0], 16)
                tea_base_rate = abs(tea_base_rate)  # Prevent negative numbers from entering invoice.

                teacher_date = schedule_date.strftime("%m/%d/%Y")
                teacher_class = lineitem.get_class_name()
                teacher_student_list = ", ".join(re.sub(RE_PARENTHESIS, "", name) for name in excluded_cxl_list)
                teacher_rate = tea_base_rate
                teacher_hour = delta
                teacher_amount = tea_base_rate * delta
                teacher_no_show = is_noshow_valid

                tea_invoice = CalendarData_Invoice_LinkedList(teacher_date, teacher_class, teacher_student_list,
                                                              teacher_rate, teacher_hour, teacher_amount, teacher_no_show)
                teacher_invoice.store_calendar_invoice_data(re_fixed_teacher, tea_invoice)

            self._invoice_database.create_teacher_info(re_fixed_teacher)

        teacher_invoice.write_invoice_to_excel()
        teacher_invoice.__del__()