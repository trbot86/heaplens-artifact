/* Author-only phase markers, identical in the logging and non-logging builds. */
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <string.h>
#include <stdio.h>
#ifdef __cplusplus
extern "C" {
#endif
extern void memhook_wait_phase(int) __attribute__((weak));
#ifdef __cplusplus
}
#endif
static int hl_control_fd = -1, hl_ack_fd = -1;
static void hl_gate_init(void) {
    const char *ctl = getenv("HL_PERF_CONTROL"), *ack = getenv("HL_PERF_ACK");
    if (!ctl || !ack) { fprintf(stderr,"Missing perf control paths\n"); exit(93); }
    hl_control_fd = open(ctl, O_RDWR);
    hl_ack_fd = open(ack, O_RDWR);
    if (hl_control_fd < 0 || hl_ack_fd < 0) exit(94);
}
static void hl_counter_gate(int enabled) {
    const char *cmd = enabled ? "enable\n" : "disable\n";
    if (write(hl_control_fd,cmd,strlen(cmd)) != (ssize_t)strlen(cmd)) exit(95);
    struct pollfd pfd = {hl_ack_fd, POLLIN, 0};
    char answer[16]; int used=0;
    do {
        char ch;
        if (poll(&pfd,1,10000) != 1 || read(hl_ack_fd,&ch,1) != 1) exit(96);
        /* perf versions may write sizeof("ack\\n"), including the trailing NUL. */
        if (!ch) continue;
        answer[used++]=ch;
        if (ch=='\n') break;
    } while (used < 15);
    answer[used]=0;
    if (strcmp(answer,"ack\n")) exit(97);
    fprintf(stderr,"HL_COUNTER_GATE %s",cmd);
}
static void hl_worker_phase(int phase) {
    if (memhook_wait_phase) memhook_wait_phase(phase);
}
