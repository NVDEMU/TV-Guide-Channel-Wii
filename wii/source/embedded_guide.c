/*
 * Build-time guide snapshot.
 * tools/build_tvmaze_guide.py replaces embedded_guide_data.inc in CI.
 * The committed include is an unmistakably synthetic offline fallback.
 */
#include <string.h>
#include "embedded_guide.h"
#include "embedded_guide_data.inc"

const char *embedded_guide_text(const char *timezone_name) {
    if (timezone_name == NULL) return guide_eastern;
    if (strcmp(timezone_name, "America/Chicago") == 0) return guide_central;
    if (strcmp(timezone_name, "America/Denver") == 0) return guide_mountain;
    if (strcmp(timezone_name, "America/Los_Angeles") == 0) return guide_pacific;
    return guide_eastern;
}
