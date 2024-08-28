'''Note to self: JSON only stores locally. Might plan on setting up SQL in order for other front desk users to access.'''

import json
import tkinter as tk
from tkinter import messagebox, ttk

_JSON_FILENAME = "hourly_rates.json"

class BostonEdu_HourlyRates_Offline:
    def __init__(self):
        self._person_name = ""
        self._subject = ""
        self._rate_amount = 0.0

    def _new_teacher_prompt_screen(self) -> bool:
        teacher_prompt_screen_messagebox = messagebox.askyesno(title="Invoice Editor", message="No matching teacher named {} found in {}! Generate?".format(self._person_name, self._subject))
        return teacher_prompt_screen_messagebox

    def _new_subject_rate_prompt_screen(self) -> bool:
        subject_prompt_screen_messagebox = messagebox.askyesno(title="Invoice Editor", message="No matching subject named, {}, found for person named, {} to find a rate! Generate?".format(self._subject, self._person_name))
        return subject_prompt_screen_messagebox

    def _minimum_wage_warning_prompt(self) -> bool:
        wage_prompt_screen_messagebox = messagebox.askyesno(title="Invoice Editor", message="Value below $20 are not advised. Continue anyway?")
        return wage_prompt_screen_messagebox

    def _subject_removal_warning_prompt(self) -> bool:
        subject_removal_warning_screen_messagebox = messagebox.askyesno(title="Invoice Editor", message="WARNING: At least one rates are included in this subject and you are about to permanently delete this listing! Do you wish to continue? THIS CANNOT BE UNDONE!")
        return subject_removal_warning_screen_messagebox

    def add_subject(self, subject_name: str) -> bool:
        with open(_JSON_FILENAME, "r") as open_json:
            try:
                self._rates_data = json.load(open_json)
            except json.JSONDecodeError:
                self._rates_data = {}
            # Check any existing subject before proceeding
            for k in self._rates_data.keys():
                if k.upper() == subject_name.upper():
                    return False
            self._rates_data.update({subject_name: {}})
            open_json.close()

        with open(_JSON_FILENAME, "w") as open_json:
            open_json.write(json.dumps(self._rates_data, indent=4))
            open_json.close()
        return True

    def remove_subject(self, subject_name: str) -> bool:
        try:
            with open(_JSON_FILENAME, "r") as open_json:
                try:
                    self._rates_data = json.load(open_json)
                except json.JSONDecodeError:
                    open_json.close()
                    return False
                for k, v in self._rates_data.items():
                    if k.upper() == subject_name.upper():
                        if len(v) > 0:
                            if not self._subject_removal_warning_prompt():
                                open_json.close()
                                return False
                        del self._rates_data[subject_name]
                        break

            with open(_JSON_FILENAME, "w") as open_json:
                open_json.write(json.dumps(self._rates_data, indent=4))
                open_json.close()
            return True
        except KeyError:
            open_json.close()
            return False

    def read_hourly_rates(self) -> str:
        try:
            list_of_rates_str = ""
            with open(_JSON_FILENAME, "r") as open_json:
                try:
                    json_read = json.load(open_json)
                except json.JSONDecodeError:
                    open_json.close()
                    return ""

                for k, v in json_read.items():
                    list_of_rates_str += str(k) + "\n"
                    for i, j in v.items():
                        list_of_rates_str += "\t" + str(i) + ": " + str(j) + "\n"
                open_json.close()
                return list_of_rates_str
        except FileNotFoundError:
            return ""

    def find_hourly_rates(self, person_name: str, given_subject: str, subject="Individual") -> float:
        self._person_name = person_name
        self._subject = subject
        try:
            with open(_JSON_FILENAME, "r") as open_json:
                try:
                    json_read = json.load(open_json)
                except json.JSONDecodeError:
                    raise KeyError
                # Find rate overrides by subject names.
                for k in json_read.keys():
                    if k.upper() == "INDIVIDUAL" or k.upper() == "GROUP":
                        continue
                    if k.upper() == given_subject.upper():
                        self._subject = k
                        break
                for k, v in json_read[self._subject].items():
                    if k.upper() == self._person_name.upper():
                        open_json.close()
                        return v
                open_json.close()
            if not self._new_teacher_prompt_screen():
                return 0.0
            self._display_rates_value()
        except FileNotFoundError:
            with open(_JSON_FILENAME, "x") as new_json:
                new_json.close()
            self.find_hourly_rates(person_name, subject)
        except KeyError:
            if not self._new_subject_rate_prompt_screen():
                return 0.0
            self._display_rates_value()
        return self._rate_amount

    def _write_hourly_rates(self) -> None:
        try:
            self._rate_amount = float(self._hourly_rate_amount.get())
            if self._rate_amount < 20.0:
                if not self._minimum_wage_warning_prompt():
                    raise ValueError
            with open(_JSON_FILENAME, "r") as open_json:
                try:
                    self._rates_data = json.load(open_json)
                    self._rates_data[self._subject].update({self._person_name: self._rate_amount})
                    self._rates_data[self._subject] = dict(sorted(self._rates_data[self._subject].items(), key=lambda x: x[0]))
                except json.JSONDecodeError:
                    self._rates_data = {}
                    self._rates_data[self._subject] = {self._person_name: self._rate_amount}
                except KeyError:
                    self._rates_data[self._subject] = {self._person_name: self._rate_amount}
                open_json.close()
        except ValueError:
            self._window.quit()
            self._window.destroy()
            self._display_rates_value()


        with open(_JSON_FILENAME, "w") as open_json:
            open_json.write(json.dumps(self._rates_data, indent=4))
            open_json.close()
        self._window.quit()
        self._window.destroy()

    def _display_rates_value(self) -> None:
        self._window = tk.Tk()
        self._window.resizable(False, False)
        hourly_rate_text_label = tk.Label(self._window, text="Enter the {} hourly rate for {}.".format(self._subject, self._person_name))
        hourly_rate_text_label.grid(row=0, column=0, columnspan=2, padx=10, pady=10)

        self._hourly_rates_var = tk.DoubleVar()
        self._hourly_rate_amount = ttk.Entry(self._window, textvariable=self._hourly_rates_var)
        self._hourly_rate_amount.grid(row=1, column=0, padx=10, pady=10)

        submit_button = ttk.Button(self._window, text="Submit", command=self._write_hourly_rates)
        submit_button.grid(row=1, column=1, sticky=tk.W + tk.E, padx=10, pady=10)
        self._window.mainloop()
