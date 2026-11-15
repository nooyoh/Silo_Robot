#ifndef SILO_PROTOCOL_H
#define SILO_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum {
    SILO_CONTROL_FRAME_SIZE = 6,
    SILO_TELEMETRY_FRAME_SIZE = 8,
    SILO_FRAME_END = 0x55,
    SILO_CONTROL_HEADER = 0xAA,
    SILO_TELEMETRY_HEADER = 0xBB,
    SILO_TELEMETRY_TYPE = 0x01
};

typedef enum {
    SILO_CMD_MOVE = 0x01,
    SILO_CMD_STOP = 0x02,
    SILO_CMD_STOP_RELEASE = 0x03
} SiloCommandType;

typedef struct {
    SiloCommandType type;
    int8_t throttle;
    int8_t turn;
} SiloCommand;

typedef struct {
    uint8_t bytes[SILO_CONTROL_FRAME_SIZE];
    uint8_t length;
} SiloProtocolParser;

void silo_protocol_init(SiloProtocolParser *parser);
bool silo_protocol_push_byte(SiloProtocolParser *parser, uint8_t byte, SiloCommand *command);
size_t silo_protocol_make_telemetry(uint8_t distance_1_mm,
                                    uint8_t distance_2_mm,
                                    uint8_t distance_3_mm,
                                    uint8_t flags,
                                    uint8_t output[SILO_TELEMETRY_FRAME_SIZE]);

#endif

