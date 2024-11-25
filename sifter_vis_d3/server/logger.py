import os
import simplejson as json

class Logger:
    @staticmethod
    def get_log_files():
        return os.listdir("./saved_state/")

    def __init__(self, fname):
        self.fname = fname

    def __del__(self):
        return

    def log(self, data_to_save):
        with open("saved_state/{}_save.json".format(self.fname.split(".")[0]), 'w') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        return "OK"
    
    def get_notes(self):
        data = dict()
        with open("saved_state/{}_save.json".format(self.fname.split(".")[0]), 'r') as f:
            data= json.load(f)
        return data["myNotes"]