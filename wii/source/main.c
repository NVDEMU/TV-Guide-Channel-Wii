/*
 * TV Guide USA - US-English Wii homebrew channel frontend.
 *
 * This is a new, open implementation inspired by the TV no Tomo guide concept;
 * it does not contain Nintendo's proprietary channel code. Guide data comes
 * from this project's text endpoint. The current HTTP client is intended for
 * local-network development only; do not send private information over HTTP.
 */
#include <gccore.h>
#include <ogc/if_config.h>
#include <wiiuse/wpad.h>
#include <fat.h>

#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define MAX_CHANNELS 16
#define MAX_PROGRAMMES 64
#define RESPONSE_SIZE 16384
#define CONFIG_PATH "sd:/apps/tv-guide-channel-wii/config.ini"
#define DEFAULT_SERVER "192.168.1.2"
#define DEFAULT_PORT 8000

typedef struct {
    char id[64];
    char name[80];
} GuideChannel;

typedef struct {
    char channel_id[64];
    char start[16];
    char end[16];
    char title[120];
    char description[200];
} GuideProgramme;

typedef struct {
    GuideChannel channels[MAX_CHANNELS];
    GuideProgramme programmes[MAX_PROGRAMMES];
    int channel_count;
    int programme_count;
    char mode[8];
    char server[64];
    char timezone[40];
    int port;
} GuideState;

static GuideState guide;
static void *framebuffer;
static GXRModeObj *video_mode;
static int selected_channel;
static int selected_programme;
static bool show_details;
static const char *US_TIMEZONES[] = {
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles"
};
static const int US_TIMEZONE_COUNT = 4;

static void copy_text(char *destination, size_t size, const char *source) {
    if (size == 0) return;
    if (!source) source = "";
    snprintf(destination, size, "%s", source);
}

static void initialise_video(void) {
    VIDEO_Init();
    WPAD_Init();
    video_mode = VIDEO_GetPreferredMode(NULL);
    framebuffer = MEM_K0_TO_K1(SYS_AllocateFramebuffer(video_mode));
    console_init(framebuffer, 20, 20, video_mode->fbWidth,
                 video_mode->xfbHeight,
                 video_mode->fbWidth * VI_DISPLAY_PIX_SZ);
    VIDEO_Configure(video_mode);
    VIDEO_SetNextFramebuffer(framebuffer);
    VIDEO_SetBlack(false);
    VIDEO_Flush();
    VIDEO_WaitVSync();
    if (video_mode->viTVMode & VI_NON_INTERLACE) VIDEO_WaitVSync();
}

static void load_configuration(void) {
    copy_text(guide.server, sizeof(guide.server), DEFAULT_SERVER);
    copy_text(guide.timezone, sizeof(guide.timezone), US_TIMEZONES[0]);
    guide.port = DEFAULT_PORT;
    copy_text(guide.mode, sizeof(guide.mode), "DEMO");

    if (!fatInitDefault()) {
        return;
    }

    FILE *file = fopen(CONFIG_PATH, "r");
    if (!file) return;

    char line[256];
    while (fgets(line, sizeof(line), file)) {
        char *newline = strpbrk(line, "\r\n");
        if (newline) *newline = '\0';
        if (strncmp(line, "server=", 7) == 0 && line[7] != '\0') {
            copy_text(guide.server, sizeof(guide.server), line + 7);
        } else if (strncmp(line, "port=", 5) == 0) {
            int port = atoi(line + 5);
            if (port > 0 && port <= 65535) guide.port = port;
        } else if (strncmp(line, "timezone=", 9) == 0) {
            for (int i = 0; i < US_TIMEZONE_COUNT; ++i) {
                if (strcmp(line + 9, US_TIMEZONES[i]) == 0) {
                    copy_text(guide.timezone, sizeof(guide.timezone), US_TIMEZONES[i]);
                    break;
                }
            }
        }
    }
    fclose(file);
}

static char *next_field(char **save) {
    return strtok_r(NULL, "|", save);
}

static bool parse_guide_body(char *body) {
    guide.channel_count = 0;
    guide.programme_count = 0;
    copy_text(guide.mode, sizeof(guide.mode), "DEMO");

    char *line_save = NULL;
    for (char *line = strtok_r(body, "\n", &line_save);
         line != NULL;
         line = strtok_r(NULL, "\n", &line_save)) {
        size_t length = strlen(line);
        while (length > 0 && (line[length - 1] == '\r' || line[length - 1] == '\n')) {
            line[--length] = '\0';
        }
        char *field_save = NULL;
        char *kind = strtok_r(line, "|", &field_save);
        if (!kind) continue;

        if (strcmp(kind, "TVGUIDE") == 0) {
            (void)next_field(&field_save); /* version */
            (void)next_field(&field_save); /* locale */
            (void)next_field(&field_save); /* timezone */
            char *mode = next_field(&field_save);
            if (mode && strcmp(mode, "LIVE") == 0) {
                copy_text(guide.mode, sizeof(guide.mode), "LIVE");
            }
        } else if (strcmp(kind, "CHANNEL") == 0 &&
                   guide.channel_count < MAX_CHANNELS) {
            char *id = next_field(&field_save);
            char *name = next_field(&field_save);
            if (!id || !name) continue;
            GuideChannel *channel = &guide.channels[guide.channel_count++];
            copy_text(channel->id, sizeof(channel->id), id);
            copy_text(channel->name, sizeof(channel->name), name);
        } else if (strcmp(kind, "PROGRAM") == 0 &&
                   guide.programme_count < MAX_PROGRAMMES) {
            char *id = next_field(&field_save);
            char *start = next_field(&field_save);
            char *end = next_field(&field_save);
            char *title = next_field(&field_save);
            char *description = next_field(&field_save);
            if (!id || !start || !end || !title) continue;
            GuideProgramme *programme = &guide.programmes[guide.programme_count++];
            copy_text(programme->channel_id, sizeof(programme->channel_id), id);
            copy_text(programme->start, sizeof(programme->start), start);
            copy_text(programme->end, sizeof(programme->end), end);
            copy_text(programme->title, sizeof(programme->title), title);
            copy_text(programme->description, sizeof(programme->description), description);
        }
    }
    return guide.channel_count > 0 && guide.programme_count > 0;
}

static bool fetch_guide(void) {
    char local_ip[16] = {0};
    char netmask[16] = {0};
    char gateway[16] = {0};

    printf("Connecting to the US-English guide service...\n");
    if (if_config(local_ip, netmask, gateway, true, 10) < 0) {
        printf("Network setup failed. Loading sample listings.\n");
        return false;
    }

    struct in_addr server_address;
    if (inet_aton(guide.server, &server_address) == 0) {
        printf("Server must be an IPv4 address in config.ini.\n");
        return false;
    }

    int socket_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    if (socket_fd < 0) {
        printf("Could not create network socket.\n");
        return false;
    }

    struct timeval timeout;
    timeout.tv_sec = 5;
    timeout.tv_usec = 0;
    (void)setsockopt(socket_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    (void)setsockopt(socket_fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons((unsigned short)guide.port);
    address.sin_addr = server_address;

    if (connect(socket_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        printf("Could not connect to %s:%d.\n", guide.server, guide.port);
        close(socket_fd);
        return false;
    }

    char request[512];
    int request_length = snprintf(
        request, sizeof(request),
        "GET /api/v1/wii/guide.txt?region=us&timezone=%s HTTP/1.0\r\n"
        "Host: %s:%d\r\nAccept: text/plain\r\nConnection: close\r\n\r\n",
        guide.timezone, guide.server, guide.port);
    if (request_length <= 0 || request_length >= (int)sizeof(request) ||
        send(socket_fd, request, (size_t)request_length, 0) != request_length) {
        close(socket_fd);
        printf("Unable to send guide request.\n");
        return false;
    }

    char response[RESPONSE_SIZE];
    size_t total = 0;
    while (total + 1 < sizeof(response)) {
        int received = recv(socket_fd, response + total,
                            sizeof(response) - total - 1, 0);
        if (received == 0) break;
        if (received < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) break;
            close(socket_fd);
            printf("Guide transfer failed.\n");
            return false;
        }
        total += (size_t)received;
    }
    close(socket_fd);
    response[total] = '\0';

    char *headers_end = strstr(response, "\r\n\r\n");
    if (!headers_end || !strstr(response, "200 OK")) {
        printf("Guide server did not return HTTP 200.\n");
        return false;
    }
    headers_end += 4;
    if (!parse_guide_body(headers_end)) {
        printf("Guide response did not contain channel/programme rows.\n");
        return false;
    }
    printf("Guide loaded from server (%s).\n", guide.mode);
    return true;
}

static void add_demo_channel(const char *id, const char *name,
                             const char *title1, const char *title2) {
    if (guide.channel_count >= MAX_CHANNELS ||
        guide.programme_count + 2 > MAX_PROGRAMMES) return;

    GuideChannel *channel = &guide.channels[guide.channel_count++];
    copy_text(channel->id, sizeof(channel->id), id);
    copy_text(channel->name, sizeof(channel->name), name);

    GuideProgramme *first = &guide.programmes[guide.programme_count++];
    copy_text(first->channel_id, sizeof(first->channel_id), id);
    copy_text(first->start, sizeof(first->start), "NOW");
    copy_text(first->end, sizeof(first->end), "1 HOUR");
    copy_text(first->title, sizeof(first->title), title1);
    copy_text(first->description, sizeof(first->description),
              "Synthetic demo entry. Connect your own XMLTV feed for real listings.");

    GuideProgramme *second = &guide.programmes[guide.programme_count++];
    copy_text(second->channel_id, sizeof(second->channel_id), id);
    copy_text(second->start, sizeof(second->start), "NEXT");
    copy_text(second->end, sizeof(second->end), "LATER");
    copy_text(second->title, sizeof(second->title), title2);
    copy_text(second->description, sizeof(second->description),
              "Synthetic demo entry. Not a real broadcast schedule.");
}

static void load_demo_guide(void) {
    guide.channel_count = 0;
    guide.programme_count = 0;
    copy_text(guide.mode, sizeof(guide.mode), "DEMO");
    add_demo_channel("demo-abc", "ABC (DEMO)", "Sample National News", "Demo Entertainment");
    add_demo_channel("demo-cbs", "CBS (DEMO)", "Sample Evening News", "Demo Comedy Hour");
    add_demo_channel("demo-nbc", "NBC (DEMO)", "Sample Local News", "Demo Game Show");
    add_demo_channel("demo-fox", "FOX (DEMO)", "Sample Sports Desk", "Demo Feature Film");
    add_demo_channel("demo-pbs", "PBS (DEMO)", "Sample Public Affairs", "Demo Science");
}

static int programme_index_for_channel(int channel_index, int nth) {
    if (channel_index < 0 || channel_index >= guide.channel_count) return -1;
    int found = 0;
    for (int i = 0; i < guide.programme_count; ++i) {
        if (strcmp(guide.programmes[i].channel_id,
                   guide.channels[channel_index].id) == 0) {
            if (found == nth) return i;
            ++found;
        }
    }
    return -1;
}

static int programme_count_for_channel(int channel_index) {
    if (channel_index < 0 || channel_index >= guide.channel_count) return 0;
    int count = 0;
    for (int i = 0; i < guide.programme_count; ++i) {
        if (strcmp(guide.programmes[i].channel_id,
                   guide.channels[channel_index].id) == 0) ++count;
    }
    return count;
}

static void draw_screen(void) {
    printf("\x1b[2J\x1b[H");
    printf("===============================================================\n");
    printf("                         TV GUIDE USA                          \n");
    printf("                   ENGLISH (UNITED STATES)                     \n");
    printf("===============================================================\n");
    printf(" Source: %-4s   Time zone: %-25.25s\n",
           guide.mode, guide.timezone);
    printf(" Server: %s:%d\n", guide.server, guide.port);
    printf("---------------------------------------------------------------\n");
    printf(" CHANNELS                        SCHEDULE\n");
    printf("                                 %-28.28s\n",
           selected_channel >= 0 && selected_channel < guide.channel_count
               ? guide.channels[selected_channel].name : "Select a channel");
    printf("                                 --------------------------------\n");

    for (int row = 0; row < 10; ++row) {
        int i = row;
        if (i < guide.channel_count) {
            printf("%s %-27.27s", i == selected_channel ? ">" : " ",
                   guide.channels[i].name);
        } else {
            printf("                                ");
        }

        if (selected_channel >= 0 && selected_channel < guide.channel_count) {
            int pindex = programme_index_for_channel(selected_channel, row);
            if (pindex >= 0) {
                GuideProgramme *p = &guide.programmes[pindex];
                printf(" %s - %s  %-28.28s",
                       p->start, p->end, p->title);
            } else if (row == 0) {
                printf(" No programme data for this channel yet.");
            }
        }
        printf("\n");
    }

    if (show_details) {
        int pindex = programme_index_for_channel(selected_channel, selected_programme);
        printf("\nPROGRAM DETAILS\n");
        if (pindex >= 0) {
            GuideProgramme *p = &guide.programmes[pindex];
            printf("%s\n%s - %s\n%s\n",
                   p->title, p->start, p->end, p->description);
        } else {
            printf("No programme selected.\n");
        }
    }

    printf("---------------------------------------------------------------\n");
    printf(" UP/DOWN: Channel   LEFT/RIGHT: Programme   A: Details\n");
    printf(" 1: Refresh guide   PLUS: Cycle US time zone   B: Back\n");
    printf(" HOME: Return to Wii Menu\n");
    if (strcmp(guide.mode, "DEMO") == 0) {
        printf(" DEMO MODE: sample data only; not real television listings.\n");
    }
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    initialise_video();
    load_configuration();

    printf("\x1b[2J\x1b[H");
    printf("TV GUIDE USA\n\n");
    printf("A US-English Wii TV guide homebrew channel.\n");
    printf("Loading guide data...\n");

    if (!fetch_guide()) {
        load_demo_guide();
    }

    selected_channel = 0;
    selected_programme = 0;
    draw_screen();

    while (SYS_MainLoop()) {
        WPAD_ScanPads();
        u32 buttons = WPAD_ButtonsDown(0);
        bool redraw = false;

        if (buttons & WPAD_BUTTON_UP) {
            if (selected_channel > 0) --selected_channel;
            else if (guide.channel_count > 0) selected_channel = guide.channel_count - 1;
            selected_programme = 0;
            show_details = false;
            redraw = true;
        }
        if (buttons & WPAD_BUTTON_DOWN) {
            if (guide.channel_count > 0) {
                selected_channel = (selected_channel + 1) % guide.channel_count;
            }
            selected_programme = 0;
            show_details = false;
            redraw = true;
        }
        if (buttons & WPAD_BUTTON_LEFT) {
            int count = programme_count_for_channel(selected_channel);
            if (count > 0) selected_programme = (selected_programme + count - 1) % count;
            show_details = false;
            redraw = true;
        }
        if (buttons & WPAD_BUTTON_RIGHT) {
            int count = programme_count_for_channel(selected_channel);
            if (count > 0) selected_programme = (selected_programme + 1) % count;
            show_details = false;
            redraw = true;
        }
        if (buttons & WPAD_BUTTON_A) {
            show_details = !show_details;
            redraw = true;
        }
        if (buttons & WPAD_BUTTON_B) {
            if (show_details) {
                show_details = false;
                redraw = true;
            }
        }
        if (buttons & WPAD_BUTTON_1) {
            printf("\x1b[2J\x1b[HRefreshing guide...\n");
            if (!fetch_guide()) load_demo_guide();
            selected_channel = 0;
            selected_programme = 0;
            show_details = false;
            redraw = true;
        }
        if (buttons & WPAD_BUTTON_PLUS) {
            int current_zone = 0;
            for (int i = 0; i < US_TIMEZONE_COUNT; ++i) {
                if (strcmp(guide.timezone, US_TIMEZONES[i]) == 0) current_zone = i;
            }
            current_zone = (current_zone + 1) % US_TIMEZONE_COUNT;
            copy_text(guide.timezone, sizeof(guide.timezone), US_TIMEZONES[current_zone]);
            printf("\x1b[2J\x1b[HRefreshing guide for %s...\n", guide.timezone);
            if (!fetch_guide()) load_demo_guide();
            selected_channel = 0;
            selected_programme = 0;
            show_details = false;
            redraw = true;
        }
        if (buttons & WPAD_BUTTON_HOME) {
            break;
        }
        if (redraw) draw_screen();
        VIDEO_WaitVSync();
    }

    SYS_ResetSystem(SYS_RETURNTOMENU, 0, 0);
    return 0;
}
