#include "txn.h"
#include "row.h"
#include "row_occ.h"
#include "mem_alloc.h"
#ifdef MACROBENCH_PACK_ROW_OCC
#include "locks_impl.h"
#endif

void 
Row_occ::init(row_t * row) {
#ifndef MACROBENCH_PACK_ROW_OCC
	_row = row;
#endif
	int part_id = row->get_part_id();
#ifdef MACROBENCH_PACK_ROW_OCC
	_latch = 0;
#else
	_latch = (pthread_mutex_t *) 
		mem_allocator.alloc(sizeof(pthread_mutex_t), part_id);
	pthread_mutex_init( _latch, NULL );
#endif
	wts = 0;
	blatch = false;
}

void Row_occ::setbench_deinit() {
#ifndef MACROBENCH_PACK_ROW_OCC
    if (_latch) {
        mem_allocator.free(_latch, sizeof(pthread_mutex_t));
        _latch = NULL;
    }
#endif
}

RC
Row_occ::access(txn_man * txn, TsType type) {
	RC rc = RCOK;
#ifdef MACROBENCH_PACK_ROW_OCC
	acquireLock(&_latch);
#else
	pthread_mutex_lock( _latch );
#endif
	if (type == R_REQ) {
		if (txn->start_ts < wts)
			rc = Abort;
		else {
#ifdef MACROBENCH_PACK_ROW_OCC
			txn->cur_row->copy(reinterpret_cast<row_t*>(this));
#else
			txn->cur_row->copy(_row);
#endif
			rc = RCOK;
		}
	} else 
		assert(false);
#ifdef MACROBENCH_PACK_ROW_OCC
	releaseLock(&_latch);
#else
	pthread_mutex_unlock( _latch );
#endif
	return rc;
}

void
Row_occ::latch() {
#ifdef MACROBENCH_PACK_ROW_OCC
	acquireLock(&_latch);
#else
	pthread_mutex_lock( _latch );
#endif
}

bool
Row_occ::validate(uint64_t ts) {
	if (ts < wts) return false;
	else return true;
}

void
Row_occ::write(row_t * data, uint64_t ts) {
#ifdef MACROBENCH_PACK_ROW_OCC
	reinterpret_cast<row_t*>(this)->copy(data);
#else
	_row->copy(data);
#endif
	if (PER_ROW_VALID) {
		assert(ts > wts);
		wts = ts;
	}
}

void
Row_occ::release() {
#ifdef MACROBENCH_PACK_ROW_OCC
	releaseLock(&_latch);
#else
	pthread_mutex_unlock( _latch );
#endif
}
