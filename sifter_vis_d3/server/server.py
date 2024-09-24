from flask import Flask, request
from flask_cors import CORS, cross_origin
from sampler import Sampler
import os

db_sampler = None
app = Flask(__name__)
CORS(app)

@app.route("/get-fnames", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_fnames():
    return [fname for fname in os.listdir(os.path.dirname(os.getcwd())) if fname.endswith(".sqlite")]

@app.route("/init-sampler/<string:fname>-<int:page_size>-<int:cache_line_size>-<int:num_buckets>", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def init_sampler(fname, page_size, cache_line_size, num_buckets):
    global db_sampler
    db_sampler = Sampler(f"../{fname}", page_size, cache_line_size, num_buckets)
    return db_sampler.types() # TODO send error if init failed

@app.route("/get-lines", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_lines():
    lines_and_stats = db_sampler.get_all_lines_and_stats()
    print("Here are the lines and stats:")
    print(lines_and_stats)
    return lines_and_stats

@app.route("/get-pages/<string:cluster_alg>-<int:max_run_length>-<int:max_runs_from_cluster>", methods=["POST"])
@cross_origin(origin='http://localhost:3000')
def get_pages(cluster_alg, max_run_length, max_runs_from_cluster):
    return db_sampler.get_sample_of_pages(-1, -1, request.json, cluster_alg, max_run_length, max_runs_from_cluster)