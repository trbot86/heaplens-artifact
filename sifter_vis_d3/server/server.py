from flask import Flask

app = Flask(__name__)

@app.route("/load-data")
def load_data():
    return ""