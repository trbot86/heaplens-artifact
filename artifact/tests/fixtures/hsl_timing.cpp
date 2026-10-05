#include "hsl_timing.h"
int main() {
  HlHslTiming t;
  t.Add({105, 130, 25, false});
  t.Add({100, 125, 50, false});
  t.Add({101, 900, 10, true}); // delayed writer must not extend readers
  assert(t.readers.start_us == 100 && t.readers.finish_us == 130);
  assert(t.readers.operations == 75 && t.writers.finish_us == 900);
  assert(t.readers.workers == 2 && t.writers.workers == 1);
  t.Report({100, 910, 75, false}); // native includes post-completion time
  HlHslTiming u;
  u.Add({1, 2, 0, true}); // excluded worker first; zero operations valid
  u.Add({10, 20, 0, false});
  u.Add({12, 19, 4, false});
  assert(u.readers.start_us == 10 && u.readers.finish_us == 20);
  assert(u.readers.operations == 4 && u.writers.finish_us == 2);
  u.Report({10, 21, 4, false});
}
