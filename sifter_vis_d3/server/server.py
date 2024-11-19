from flask import Flask, request
from flask_cors import CORS, cross_origin
from sampler import Sampler
from logger import Logger
from threading import Lock
import os

app = Flask(__name__)
CORS(app)

@app.route("/get-fnames", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_fnames():
    return [fname for fname in os.listdir(os.path.dirname(os.getcwd())) if fname.endswith(".sqlite")]

@app.route("/init-app/<string:fname>-<int:page_size>-<int:cache_line_size>-<int:num_buckets>-<string:cluster_alg>-<int:max_run_length>-<int:max_runs_from_cluster>-<int:cache_size>-<int:assoc>", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def init_app(fname, page_size, cache_line_size, num_buckets, cluster_alg, max_run_length, max_runs_from_cluster, cache_size, assoc):    
    db_sampler = Sampler(f"../{fname}", page_size, cache_line_size, num_buckets)
    return {
        'types': db_sampler.types(),
        'linesAndStats': db_sampler.get_all_lines_and_stats(),
        'pagesData': db_sampler.get_sample_of_pages(-1, -1, {tp: True for tp in db_sampler.types()}, cluster_alg, max_run_length, max_runs_from_cluster),
        'cacheData': db_sampler.get_cache_data(cache_size, assoc)
    }

@app.route("/get-pages-and-cache-data/<string:fname>-<int:page_size>-<int:cache_line_size>-<int:num_buckets>-<string:cluster_alg>-<int:max_run_length>-<int:max_runs_from_cluster>-<int:cache_size>-<int:assoc>", methods=["POST"])
@cross_origin(origin='http://localhost:3000')
def get_pages_and_cache_data(fname, page_size, cache_line_size, num_buckets, cluster_alg, max_run_length, max_runs_from_cluster, cache_size, assoc):
    db_sampler = Sampler(f"../{fname}", page_size, cache_line_size, num_buckets)
    return {
        'pagesData': db_sampler.get_sample_of_pages(-1, -1, request.json, cluster_alg, max_run_length, max_runs_from_cluster),
        'cacheData': db_sampler.get_cache_data(cache_size, assoc)
    }

@app.route("/get-cache-data/<string:fname>-<int:page_size>-<int:cache_line_size>-<int:num_buckets>-<int:cache_size>-<int:assoc>", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_cache_data(fname, page_size, cache_line_size, num_buckets, cache_size, assoc):
    db_sampler = Sampler(f"../{fname}", page_size, cache_line_size, num_buckets)
    return db_sampler.get_cache_data(cache_size, assoc)

@app.route("/log-data/<string:fname>", methods=["POST"])
@cross_origin(origin='http://localhost:3000')
def log_data(fname):
    logger = Logger(fname)
    logger.log(request.json)
    return "OK"