#ifndef _MNTRACER_H
#define _MNTRACER_H

#include <linux/tracepoint.h>

DECLARE_TRACE(softirq_entry,
              TP_PROTO(unsigned int vecnr),
              TP_ARGS(vecnr));

DECLARE_TRACE(sched_switch,
              TP_PROTO(struct task_struct *prev, struct task_struct *next),
              TP_ARGS(prev, next));
#endif
