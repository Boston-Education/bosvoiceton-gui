import re

import mysql.connector
import mysql.connector.plugins.mysql_native_password
from mysql.connector import errorcode
import config_file_reader as config

_DB_NAME = "invoice"

class InvoiceDatabase:
    def __init__(self):
        config_info = config.obtain_cfg_info("config/aws_rds_database_info.cfg")
        try:
            self._rates_db = mysql.connector.connect(
                host=config_info["DATABASE_CLIENT"]["host"],
                user=config_info["DATABASE_CLIENT"]["username"],
                password=config_info["DATABASE_CLIENT"]["password"],
                port=config_info["DATABASE_CLIENT"]["port"]
            )

            self._cursor = self._rates_db.cursor()
            self._rates_db.database = _DB_NAME

        except mysql.connector.Error as err:
            # Check for database existence. Create one if it doesn't.
            if err.errno == errorcode.ER_BAD_DB_ERROR:
                print("{}! Creating a new one...".format(err.msg))
                self._cursor.execute("CREATE DATABASE {}".format(_DB_NAME))
                self._rates_db.database = _DB_NAME
            elif err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print(err.msg)
                raise
            else:
                print(err)

        self._rates_db.commit()

    def __del__(self):
        try:
            self._cursor.close()
            self._rates_db.close()
        except AttributeError:
            pass

    def get_all_student_name(self):
        self._cursor.execute("SELECT student_name FROM student")
        return self._cursor.fetchall()

    def create_student_info(self, student_name: str):
        self._cursor.execute("SELECT student_name FROM student WHERE student_name = '{}'".format(student_name.title()))
        if self._cursor.fetchall() != []:
            return False
        self._cursor.execute("INSERT INTO student (student_name) VALUES ('{}')".format(student_name.title()))
        self._rates_db.commit()
        return True

    def find_student_info(self, student_name: str):
        self._cursor.execute("SELECT student_name FROM student WHERE student_name = '{}'".format(student_name.title()))
        return self._cursor.fetchone()

    def delete_student_info(self, student_name: str):
        self.delete_discount_amount(student_name)
        self._cursor.execute("DELETE FROM student WHERE student_name = '{}'".format(student_name.title()))
        self._rates_db.commit()
        return True

    def get_all_teacher_name(self):
        self._cursor.execute("SELECT teacher_name FROM teacher")
        return self._cursor.fetchall()

    def create_teacher_info(self, teacher_name: str):
        self._cursor.execute("SELECT teacher_name FROM teacher WHERE teacher_name = '{}'".format(teacher_name.title()))
        if self._cursor.fetchall() != []:
            return False
        self._cursor.execute("INSERT INTO teacher (teacher_name) VALUES ('{}')".format(teacher_name.title()))
        self._rates_db.commit()
        return True

    # def find_student_rate(self, code_name: str):
    #     self._cursor.execute("SELECT Rate FROM student_invoice_code WHERE Code = '{}'".format(code_name))
    #     exec_result = self._cursor.fetchone()
    #     return exec_result[0] if exec_result != None else None
    #
    # def find_teacher_rate(self, code_name: str):
    #     self._cursor.execute("SELECT Rate FROM teacher_invoice_code WHERE Code = '{}'".format(code_name))
    #     exec_result = self._cursor.fetchone()
    #     return exec_result[0] if exec_result != None else None

    def create_discount_amount(self, student_name: str, amount: float):
        self._cursor.execute("SELECT student_name FROM student WHERE student_name = '{}'".format(student_name))
        if self._cursor.fetchall() != []:
            return False
        self._cursor.execute("INSERT INTO student_discount (stu_id, disc_rate)\n"
                             "SELECT id, {} FROM student WHERE student.student_name = '{}'".format(round(amount, 2), student_name))
        self._rates_db.commit()
        return True

    def get_discount_amount(self, student_name: str):
        self._cursor.execute("SELECT disc_rate FROM student_discount\n"
                             "INNER JOIN student ON student.id = student_discount.stu_id\n"
                             "WHERE student.student_name = '{}'".format(student_name))
        exec_result = self._cursor.fetchone()
        return exec_result[0] if exec_result is not None else None

    def get_all_discount_amount(self):
        self._cursor.execute("SELECT student.id, student.student_name, disc_rate FROM student_discount\n"
                             "INNER JOIN student on student.id = student_discount.stu_id")
        return self._cursor.fetchall()

    def set_discount_amount(self, student_name: str, amount: float):
        if self.get_discount_amount(student_name) is None:
            return False
        self._cursor.execute("UPDATE student_discount INNER JOIN student ON student.id = student_discount.stu_id\n"
                             "SET student_discount.disc_rate = {}\n"
                             "WHERE student.student_name = '{}'".format(amount, student_name.title()))
        self._rates_db.commit()
        return True

    def delete_discount_amount(self, student_name: str):
        if self.get_discount_amount(student_name) is None:
            return False
        self._cursor.execute("DELETE FROM student_discount WHERE stu_id = \n"
                             "(SELECT id FROM student WHERE student.student_name = '{}')".format(student_name.title()))
        self._rates_db.commit()
        return True

    # def create_tuition_amount(self, student_name: str, amount: float):
    #     self._cursor.execute("INSERT INTO tuition (stu_id, TuitionAmount)\n"
    #                          "SELECT id, {} FROM student WHERE student.student_name = '{}'".format(amount, student_name.title()))
    #     self._rates_db.commit()
    #     return True
    #
    # def get_tuition_amount(self, student_name: str):
    #     self._cursor.execute("SELECT TuitionAmount FROM tuition\n"
    #                          "INNER JOIN student ON tuition.stu_id = student.id\n"
    #                          "WHERE student.student_name = '{}'".format(student_name.title()))
    #     exec_result = self._cursor.fetchone()
    #     return exec_result[0] if exec_result != None else None
    #
    # def get_all_tuition_amount(self):
    #     self._cursor.execute("SELECT student.id, student.student_name, TuitionAmount FROM tuition\n"
    #                          "INNER JOIN student ON student.id = tuition.stu_id")
    #     return self._cursor.fetchall()
    #
    # def set_tuition_amount(self, student_name: str, amount: float):
    #     if self.get_tuition_amount(student_name) == None:
    #         return False
    #     self._cursor.execute("UPDATE tuition INNER JOIN student ON student.id = tuition.stu_id\n"
    #                          "SET tuition.TuitionAmount = {}\n"
    #                          "WHERE student.student_name = '{}'"
    #                          .format(amount, student_name.title()))
    #     self._rates_db.commit()
    #     return True

    def create_course_info(self, course_name: str):
        self._cursor.execute("SELECT course_name FROM course WHERE course_name = '{}'".format(course_name))
        if self._cursor.fetchall() != []:
            return False
        is_course_AP = bool(re.search(r"^(?:\s*)(AP)(?:\s+)", course_name.upper()))
        is_course_HONORS = bool(re.search(r"^(?:\s*)(H|HONORS)(?:\s+)", course_name.upper()))
        self._cursor.execute("INSERT INTO course (ap, honors, course_name) VALUES ({}, {}, '{}')".format(is_course_AP, is_course_HONORS, course_name.strip()))
        self._rates_db.commit()
        return True

    def get_course_info(self, course_name: str):
        self._cursor.execute("SELECT course_name FROM course WHERE course_name = '{}'".format(course_name))
        return self._cursor.fetchone()

    def delete_course_info(self, course_name: str):
        if self.get_course_info(course_name) is None:
            return False

        self._cursor.execute("DELETE FROM course WHERE course_name = '{}'".format(course_name))
        self._rates_db.commit()
        return True

    def get_all_class_name(self):
        self._cursor.execute("SELECT course_name FROM course")
        return self._cursor.fetchall()

    def get_all_class_row(self):
        self._cursor.execute("SELECT ap, honors, course_name FROM course")
        return self._cursor.fetchall()
