# devkitPPC/libogc Makefile for TV Guide USA.
.SUFFIXES:
ifeq ($(strip $(DEVKITPPC)),)
$(error "Please set DEVKITPPC in your environment. Install devkitPro's wii-dev package.")
endif

include $(DEVKITPPC)/wii_rules

TARGET := tv-guide-usa
BUILD := build
SOURCES := source
INCLUDES :=
DATA :=
LIBS := -lfat

# Override SERVER_HOST at make time if you want a different fallback address.
SERVER_HOST ?= 192.168.1.2
CFLAGS += -DTV_GUIDE_SERVER_HOST=\"$(SERVER_HOST)\"

.PHONY: all clean
all: $(TARGET).dol

clean:
	$(RM) -r $(BUILD) $(TARGET).dol $(TARGET).elf
