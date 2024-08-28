import re

import mysql.connector
import mysql.connector.plugins.mysql_native_password
from mysql.connector import errorcode
import config_file_reader as config

_DB_NAME = "invoice"
_DB_TABLES = {"student": "CREATE TABLE student ("
                         "ID INT NOT NULL AUTO_INCREMENT,"
                         "StudentName VARCHAR(255) NOT NULL,"
                         "PRIMARY KEY (ID))",
              "teacher": "CREATE TABLE teacher ("
                         "ID INT NOT NULL AUTO_INCREMENT,"
                         "TeacherName VARCHAR(255) NOT NULL,"
                         "PRIMARY KEY (ID))",
              "student_invoice_code": "CREATE TABLE student_invoice_code ("
                                      "Code CHAR(4) NOT NULL,"
                                      "Rate DOUBLE NOT NULL)",
              "teacher_invoice_code": "CREATE TABLE teacher_invoice_code ("
                                      "Code CHAR(4) NOT NULL,"
                                      "Rate DOUBLE NOT NULL)",
              "student_discount": "CREATE TABLE student_discount ("
                                  "DiscountID INT NOT NULL AUTO_INCREMENT,"
                                  "PersonID INT NOT NULL,"
                                  "DiscountRate DOUBLE,"
                                  "PRIMARY KEY (DiscountID),"
                                  "FOREIGN KEY (PersonID) REFERENCES student(ID))",
              "course": "CREATE TABLE course ("
                        "AP BOOLEAN NOT NULL,"
                        "HONORS BOOLEAN NOT NULL,"
                        "CourseName VARCHAR(255) NOT NULL)"}

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

        # Check for existing tables. If not, create one.
        print("Checking table existence/error...")
        for name, table in _DB_TABLES.items():
            try:
                self._cursor.execute(table)
                print("No table named {} found in {}. Generating...".format(name, _DB_NAME))
                if name == "student_invoice_code" or name == "teacher_invoice_code":
                    rate_num_loop = 20
                    self._cursor.execute("INSERT INTO {} (Code, Rate) VALUES ('{}', {})".format(name, name[0].title() + "0", 0))
                    for i in range(1, 26):
                        self._cursor.execute("INSERT INTO {} (Code, Rate) VALUES ('{}', {})"
                                             .format(name, name[0].title() + str(i), rate_num_loop))
                        rate_num_loop += 5
            except mysql.connector.Error as err:
                # I could say to just use IF NOT EXISTS but should work for now.
                if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                    pass
                else:
                    print(err)
        self._rates_db.commit()
        print("Done!")

    def __del__(self):
        try:
            self._cursor.close()
            self._rates_db.close()
        except AttributeError:
            pass

    def get_all_student_name(self):
        self._cursor.execute("SELECT StudentName FROM student")
        return self._cursor.fetchall()

    def create_student_info(self, student_name: str):
        self._cursor.execute("SELECT StudentName FROM student WHERE StudentName = '{}'".format(student_name.title()))
        if self._cursor.fetchall() != []:
            return False
        self._cursor.execute("INSERT INTO student (StudentName) VALUES ('{}')".format(student_name.title()))
        self._rates_db.commit()
        return True

    def find_student_info(self, student_name: str):
        self._cursor.execute("SELECT StudentName FROM student WHERE StudentName = '{}'".format(student_name.title()))
        return self._cursor.fetchone()

    def delete_student_info(self, student_name: str):
        self.delete_discount_amount(student_name)
        self._cursor.execute("DELETE FROM student WHERE StudentName = '{}'".format(student_name.title()))
        self._rates_db.commit()
        return True

    def get_all_teacher_name(self):
        self._cursor.execute("SELECT TeacherName FROM teacher")
        return self._cursor.fetchall()

    def create_teacher_info(self, teacher_name: str):
        self._cursor.execute("SELECT TeacherName FROM teacher WHERE TeacherName = '{}'".format(teacher_name.title()))
        if self._cursor.fetchall() != []:
            return False
        self._cursor.execute("INSERT INTO teacher (TeacherName) VALUES ('{}')".format(teacher_name.title()))
        self._rates_db.commit()
        return True

    def find_student_rate(self, code_name: str):
        self._cursor.execute("SELECT Rate FROM student_invoice_code WHERE Code = '{}'".format(code_name))
        exec_result = self._cursor.fetchone()
        return exec_result[0] if exec_result != None else None

    def find_teacher_rate(self, code_name: str):
        self._cursor.execute("SELECT Rate FROM teacher_invoice_code WHERE Code = '{}'".format(code_name))
        exec_result = self._cursor.fetchone()
        return exec_result[0] if exec_result != None else None

    def create_discount_amount(self, student_name: str, amount: float):
        self._cursor.execute("INSERT INTO student_discount (PersonID, DiscountRate)\n"
                             "SELECT ID, {} FROM student WHERE student.StudentName = '{}'".format(round(amount, 2), student_name))
        self._rates_db.commit()
        return True

    def get_discount_amount(self, student_name: str):
        self._cursor.execute("SELECT DiscountRate FROM student_discount\n"
                             "INNER JOIN student ON student.ID = student_discount.PersonID\n"
                             "WHERE student.StudentName = '{}'".format(student_name))
        exec_result = self._cursor.fetchone()
        return exec_result[0] if exec_result != None else None

    def get_all_discount_amount(self):
        self._cursor.execute("SELECT student.ID, student.StudentName, DiscountRate FROM student_discount\n"
                             "INNER JOIN student on student.ID = student_discount.PersonID")
        return self._cursor.fetchall()

    def set_discount_amount(self, student_name: str, amount: float):
        if self.get_discount_amount(student_name) == None:
            return False
        self._cursor.execute("UPDATE student_discount INNER JOIN student ON student.ID = student_discount.PersonID\n"
                             "SET student_discount.DiscountRate = {}\n"
                             "WHERE student.StudentName = '{}'".format(amount, student_name.title()))
        self._rates_db.commit()
        return True

    def delete_discount_amount(self, student_name: str):
        if self.get_discount_amount(student_name) == None:
            return False
        self._cursor.execute("DELETE FROM student_discount WHERE PersonID = \n"
                             "(SELECT ID FROM student WHERE student.StudentName = '{}')".format(student_name.title()))
        self._rates_db.commit()
        return True

    # def create_tuition_amount(self, student_name: str, amount: float):
    #     self._cursor.execute("INSERT INTO tuition (PersonID, TuitionAmount)\n"
    #                          "SELECT ID, {} FROM student WHERE student.StudentName = '{}'".format(amount, student_name.title()))
    #     self._rates_db.commit()
    #     return True
    #
    # def get_tuition_amount(self, student_name: str):
    #     self._cursor.execute("SELECT TuitionAmount FROM tuition\n"
    #                          "INNER JOIN student ON tuition.PersonID = student.ID\n"
    #                          "WHERE student.StudentName = '{}'".format(student_name.title()))
    #     exec_result = self._cursor.fetchone()
    #     return exec_result[0] if exec_result != None else None
    #
    # def get_all_tuition_amount(self):
    #     self._cursor.execute("SELECT student.ID, student.StudentName, TuitionAmount FROM tuition\n"
    #                          "INNER JOIN student ON student.ID = tuition.PersonID")
    #     return self._cursor.fetchall()
    #
    # def set_tuition_amount(self, student_name: str, amount: float):
    #     if self.get_tuition_amount(student_name) == None:
    #         return False
    #     self._cursor.execute("UPDATE tuition INNER JOIN student ON student.ID = tuition.PersonID\n"
    #                          "SET tuition.TuitionAmount = {}\n"
    #                          "WHERE student.StudentName = '{}'"
    #                          .format(amount, student_name.title()))
    #     self._rates_db.commit()
    #     return True

    def get_student_code(self):
        self._cursor.execute("SELECT * FROM student_invoice_code")
        return self._cursor.fetchall()

    def get_teacher_code(self):
        self._cursor.execute("SELECT * FROM teacher_invoice_code")
        return self._cursor.fetchall()

    def create_course_info(self, course_name: str):
        is_course_AP = bool(re.search(r"^(?:\s*)(AP)(?:\s+)", course_name.upper()))
        is_course_HONORS = bool(re.search(r"^(?:\s*)(H|HONORS)(?:\s+)", course_name.upper()))
        self._cursor.execute("SELECT CourseName FROM course WHERE CourseName = '{}'".format(course_name))
        if self._cursor.fetchall() != []:
            return False
        self._cursor.execute("INSERT INTO course (AP, HONORS, CourseName) VALUES ({}, {}, '{}')".format(is_course_AP, is_course_HONORS, course_name.strip()))
        self._rates_db.commit()
        return True

    def get_all_class_name(self):
        self._cursor.execute("SELECT CourseName FROM course")
        return self._cursor.fetchall()

    def get_all_class_row(self):
        self._cursor.execute("SELECT * FROM course")
        return self._cursor.fetchall()

# if __name__ == "__main__":
#     print(InvoiceDatabase().create_discount_amount("Ruleon Lee", 0.3))