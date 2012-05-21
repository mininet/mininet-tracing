
#undef TRACE_SYSTEM
#define TRACE_SYSTEM mininet

#if !defined(_TRACE_EVENT_MININET_H) || defined(TRACE_HEADER_MULTI_READ)
#define _TRACE_EVENT_MININET_H

#include <linux/tracepoint.h>

TRACE_EVENT(mn_htb_dequeue,

            TP_PROTO(const char *link),

            TP_ARGS(link),

            TP_STRUCT__entry(
                             __array(char, link, 32)
                             ),

            TP_fast_assign(
                           strncpy(__entry->link, link, 32);
                           ),

            TP_printk("link: %s", __entry->link)
            );

#endif

#undef TRACE_INCLUDE_PATH
#undef TRACE_INCLUDE_FILE
#define TRACE_INCLUDE_PATH .
#define TRACE_INCLUDE_FILE htb_trace

#include <trace/define_trace.h>
