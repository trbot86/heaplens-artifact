import sqlite3
import simplejson as json

class Logger:
    def __init__(self, fname):
        self.con = sqlite3.connect(fname)

    def __del__(self):
        self.con.close()

    def log(self, jsonData):
        data = json.loads(jsonData)
        cursor = self.con.cursor()
        cursor.execute("DROP TABLE IF EXISTS NOTES")
        cursor.execute("DROP TABLE IF EXISTS COLOURS")
        cursor.execute("""CREATE TABLE IF NOT EXISTS NOTES(
                            My_Notes    TEXT
                        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS COLOURS(
                            Type        TEXT,
                            Colour      TEXT
                        )""")
        cursor.execute("INSERT INTO NOTES (My_Notes) VALUES(?)",
                    [data["myNotes"]])
        for entry in data["colours"]:
            cursor.execute("INSERT INTO COLOURS (Type, Colour) VALUES(?, ?)",
                        [entry["type"], entry["colour"]])
        self.con.commit()