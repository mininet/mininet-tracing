
#undef TRACE_SYSTEM
#define TRACE_SYSTEM mininet

#if !defined(_TRACE_EVENT_MININET_H) || defined(TRACE_HEADER_MULTI_READ)
#define _TRACE_EVENT_MININET_H

#include <linux/tracepoint.h>

TRACE_EVENT(mn_htb,

            TP_PROTO(const char *action, const char *link, int len),

            TP_ARGS(action, link, len),

            TP_STRUCT__entry(
                             __array(char, action, 32)
                             __array(char, link, 32)
                             __field(int, len)
                             ),

            TP_fast_assign(
                           strncpy(__entry->action, action, 32);
                           strncpy(__entry->link, link, 32);
                           __entry->len = len;
                           ),

            TP_printk("action: %s, link: %s, len: %d", __entry->action, __entry->link, __entry->len)
            );

#endif

#undef TRACE_INCLUDE_PATH
#undef TRACE_INCLUDE_FILE
#define TRACE_INCLUDE_PATH .
#define TRACE_INCLUDE_FILE htb_trace

#include <trace/define_trace.h>
