#ifndef ROW_OCC_H
#define ROW_OCC_H
#ifdef MACROBENCH_PACK_ROW_OCC
#include "locks_impl.h"
#endif

class table_t;
class Catalog;
class txn_man;
struct TsReqEntry;

class Row_occ {
public:
	void 				init(row_t * row);
	void 				setbench_deinit();
	RC 					access(txn_man * txn, TsType type);
	void 				latch();
	// ts is the start_ts of the validating txn 
	bool				validate(uint64_t ts);
	void				write(row_t * data, uint64_t ts);
	void 				release();
private:
#ifdef MACROBENCH_PACK_ROW_OCC
	volatile int _latch;
	// char padlatch[4];
#else
 	pthread_mutex_t * 	_latch;
#endif
	bool 				blatch;

	row_t * 			_row;
	// the last update time
	ts_t 				wts;

#ifdef MACROBENCH_PAD_OCC
	char padding[32];
#endif
};

#endif
