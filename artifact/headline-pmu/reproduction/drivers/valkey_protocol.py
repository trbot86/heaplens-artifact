"""Fixed headline client commands and acknowledged perf-gate helper.

Gate timestamps bound the transition; they are not claimed to be the exact
kernel enable/disable instant. The runner must preserve both bounds and report
that the server PMU window encloses client startup, load, and client teardown.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import os
import select
import time


def client_command(binary, port, output, preload=False):
    command = ['numactl','--physcpubind='+cpus(24,1),'--membind='+str(node(1)),str(binary),
               '--server=127.0.0.1','--port='+str(port),'--protocol=redis',
               '--threads=24','--clients=4','--pipeline=16','--key-prefix=heaplens:',
               '--key-minimum=1','--key-maximum=4000000','--data-size=128',
               '--distinct-client-seed','--hide-histogram']
    command += (['--ratio=1:0','--key-pattern=P:P','--requests=allkeys'] if preload else
                ['--ratio=1:4','--key-pattern=R:R','--test-time=30'])
    return command + ['--json-out-file='+str(output)]


class PerfGate:
    def __init__(self, control, ack):
        self.control = os.open(control, os.O_RDWR | os.O_NONBLOCK)
        try:
            self.ack = os.open(ack, os.O_RDWR | os.O_NONBLOCK)
        except BaseException:
            os.close(self.control)
            raise
        self.enabled = False

    def transition(self, enable, timeout=10):
        if enable == self.enabled:
            raise ValueError('duplicate perf gate transition')
        if select.select([self.ack], [], [], 0)[0]:
            # Some perf versions include the C-string trailing NUL.
            if os.read(self.ack,64).strip(b'\0'):
                raise RuntimeError('unexpected stale perf acknowledgement')
        message = b'enable\n' if enable else b'disable\n'
        before = time.monotonic_ns()
        if os.write(self.control, message) != len(message):
            raise RuntimeError('short perf control write')
        deadline = time.monotonic()+timeout
        response = b''
        while not response.endswith(b'\n'):
            left = deadline-time.monotonic()
            if left <= 0 or not select.select([self.ack], [], [], left)[0]:
                raise TimeoutError('perf acknowledgement timeout')
            response += os.read(self.ack, 64).replace(b'\0',b'')
            if len(response) > 64:
                raise RuntimeError('oversized perf acknowledgement')
        after = time.monotonic_ns()
        if response != b'ack\n':
            raise RuntimeError('unexpected perf acknowledgement: '+repr(response))
        self.enabled = enable
        return dict(action=message.decode().strip(), before_ns=before,
                    after_ns=after, transition_uncertainty_ns=after-before)

    def close(self):
        os.close(self.control)
        os.close(self.ack)
