import re

def split_calendar_title(title: str) -> list:
    """
    Converts a string into a list based on the following regular expression separation.

    :param title: A Calendar title based on this format:
    [Optional Modifier - CXL/NS] - [Teacher’s Full Name, First Last] - [Student names separated by comma, First, Last] - [Name of the class]  - [Codename T#S#] - [Modality]
    :return: A list separated based on calendar format
    """

    title_sep = re.split(r"(?:\s*)-+(?:\s*)", title)

    # For consistency
    if title_sep[0].upper() != "CXL" and title_sep[0].upper() != "NS":
        title_sep.insert(0, "")
    if not re.search(r"^T(\d+)(\*?)S(\d+)(\*?)$", title_sep[4].upper().replace(" ", "")):
        raise Exception("ERROR: Improper code format currently read as {} for: {}! Skipping...".format(title_sep[4], title))

    if len(title_sep) > 6:
        print("WARNING: More than 6 variables included: {}! Results may not be accurate!".format(title))
    return title_sep

class LineItem:
    def __init__(self, title):
        title_split = split_calendar_title(title)
        self._isCanceled = title_split[0].upper() == "CXL"
        self._teacher_name = title_split[1]
        self._student_names = re.split(r",(?:\s*)", title_split[2])
        self._class_name = title_split[3]
        self._code_names = title_split[4].upper().replace(" ", "")
        self._modality = title_split[5]

        self._is_no_show = title_split[0].upper() == "NS"

    def get_canceled_status(self):
        return self._isCanceled

    def get_teacher_name(self):
        return self._teacher_name

    def get_student_names(self):
        return self._student_names

    def get_class_name(self):
        return self._class_name

    def get_code_names(self):
        return self._code_names

    def get_modality(self):
        return self._modality

    def get_no_show_status(self):
        return self._is_no_show