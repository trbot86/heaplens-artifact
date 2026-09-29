from flask import Flask, request
from flask_cors import CORS, cross_origin
from sampler import Sampler
from logger import Logger
from cache_limits import CacheRequestError, CacheBudgetExceeded, validate_cache_geometry
from page_selection import DEFAULT_PAGE_BUDGET, DEFAULT_RECORD_BUDGET
import os

app = Flask(__name__)
CORS(app)


@app.errorhandler(CacheRequestError)
def cache_request_error(error):
    return {'error': str(error)}, 413 if isinstance(error, CacheBudgetExceeded) else 400


@app.errorhandler(MemoryError)
def memory_error(error):
    return {'error': 'Not enough memory to prepare this view. Try fewer time buckets. The previous view is unchanged.'}, 503


def cache_sampler(fname, page_size, cache_line_size, num_buckets, cache_size, assoc):
    validate_cache_geometry(page_size, cache_line_size, num_buckets, cache_size, assoc)
    return Sampler(f"../{fname}", page_size, cache_line_size, num_buckets)


def page_budgets():
    limits = {}
    for name, default in (('page_budget', DEFAULT_PAGE_BUDGET),
                          ('record_budget', DEFAULT_RECORD_BUDGET)):
        raw = request.args.get(name, str(default))
        if not raw.isascii() or not raw.isdigit() or int(raw) < 1:
            raise CacheRequestError(f'{name} must be a positive integer.')
        limits[name] = int(raw)
    return limits


@app.route("/get-fnames", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_fnames():
    return [fname for fname in os.listdir(os.path.dirname(os.getcwd())) if fname.endswith(".sqlite")]


@app.route("/init-app/<string:fname>-<int:page_size>-<int:cache_line_size>-<int:num_buckets>-<string:cluster_alg>-<int:max_run_length>-<int:max_runs_from_cluster>-<int:cache_size>-<int:assoc>", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def init_app(fname, page_size, cache_line_size, num_buckets, cluster_alg, max_run_length, max_runs_from_cluster, cache_size, assoc):    
    budgets = page_budgets()
    db_sampler = cache_sampler(fname, page_size, cache_line_size, num_buckets, cache_size, assoc)
    return {
        'types': db_sampler.types(),
        'linesAndStats': db_sampler.get_all_lines_and_stats(),
        'pagesData': db_sampler.get_sample_of_pages(-1, -1, {tp: True for tp in db_sampler.types()}, cluster_alg, max_run_length, max_runs_from_cluster, **budgets),
        'cacheData': db_sampler.get_cache_data(cache_size, assoc)
    }


@app.route("/get-pages-and-cache-data/<string:fname>-<int:page_size>-<int:cache_line_size>-<int:num_buckets>-<string:cluster_alg>-<int:max_run_length>-<int:max_runs_from_cluster>-<int:cache_size>-<int:assoc>", methods=["POST"])
@cross_origin(origin='http://localhost:3000')
def get_pages_and_cache_data(fname, page_size, cache_line_size, num_buckets, cluster_alg, max_run_length, max_runs_from_cluster, cache_size, assoc):
    budgets = page_budgets()
    db_sampler = cache_sampler(fname, page_size, cache_line_size, num_buckets, cache_size, assoc)
    return {
        'pagesData': db_sampler.get_sample_of_pages(-1, -1, request.json, cluster_alg, max_run_length, max_runs_from_cluster, **budgets),
        'cacheData': db_sampler.get_cache_data(cache_size, assoc)
    }


@app.route("/get-cache-data/<string:fname>-<int:page_size>-<int:cache_line_size>-<int:num_buckets>-<int:cache_size>-<int:assoc>", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_cache_data(fname, page_size, cache_line_size, num_buckets, cache_size, assoc):
    db_sampler = cache_sampler(fname, page_size, cache_line_size, num_buckets, cache_size, assoc)
    return db_sampler.get_cache_data(cache_size, assoc)


@app.route("/log-data/<string:fname>", methods=["POST"])
@cross_origin(origin='http://localhost:3000')
def log_data(fname):
    logger = Logger(fname)
    return logger.log(request.json)


@app.route("/log-data/get-files", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_log_files():
    return Logger.get_log_files()


@app.route("/log-data/get-notes/<string:fname>", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_notes_for_file(fname):
    logger = Logger(fname)
    return logger.get_notes()


@app.route("/log-data/get-colours/<string:fname>", methods=["GET"])
@cross_origin(origin='http://localhost:3000')
def get_colours_for_file(fname):
    logger = Logger(fname)
    return logger.get_colours()
