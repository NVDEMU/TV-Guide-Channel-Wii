#ifndef TV_GUIDE_EMBEDDED_GUIDE_H
#define TV_GUIDE_EMBEDDED_GUIDE_H

/* Return a writable copy is not guaranteed; callers must copy before parsing. */
const char *embedded_guide_text(const char *timezone_name);

#endif
