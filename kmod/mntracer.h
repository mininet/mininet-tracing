
#undef TRACE_SYSTEM
#define TRACE_SYSTEM mininet

#if !defined(_TRACE_EVENT_MININET_H) || defined(TRACE_HEADER_MULTI_READ)
#define _TRACE_EVENT_MININET_H

#include <linux/tracepoint.h>

TRACE_EVENT(mn_sched_switch,

            TP_PROTO(int cpu, const char *prev_container, const char *next_container),

            TP_ARGS(cpu, prev_container, next_container),

            TP_STRUCT__entry(
                             __field(int, cpu)
                             __array(char, prev_container, 32)
                             __array(char, next_container, 32)
                             ),

            TP_fast_assign(
                           __entry->cpu = cpu;
                           strncpy(__entry->prev_container, prev_container, 32);
                           strncpy(__entry->next_container, next_container, 32);
                           ),

            TP_printk("cpu %d, prev: %s, next: %s", __entry->cpu, __entry->prev_container, __entry->next_container)
            );

/* We still need this to hook into the existing sched_switch
   tracepoint */
DECLARE_TRACE(sched_switch,
              TP_PROTO(struct task_struct *prev, struct task_struct *next),
              TP_ARGS(prev, next));

#endif

#undef TRACE_INCLUDE_PATH
#undef TRACE_INCLUDE_FILE
#define TRACE_INCLUDE_PATH .
#define TRACE_INCLUDE_FILE mntracer

#include <trace/define_trace.h>
