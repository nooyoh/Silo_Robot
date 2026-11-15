#include "silo_protocol.h"

static uint8_t control_checksum(const uint8_t frame[SILO_CONTROL_FRAME_SIZE])
{
    return (uint8_t)(frame[1] ^ frame[2] ^ frame[3]);
}

void silo_protocol_init(SiloProtocolParser *parser)
{
    parser->length = 0;
}

bool silo_protocol_push_byte(SiloProtocolParser *parser, uint8_t byte, SiloCommand *command)
{
    if (parser->length == 0) {
        if (byte == SILO_CONTROL_HEADER) {
            parser->bytes[0] = byte;
            parser->length = 1;
        }
        return false;
    }

    parser->bytes[parser->length++] = byte;
    if (parser->length < SILO_CONTROL_FRAME_SIZE) {
        return false;
    }

    parser->length = 0;
    if (parser->bytes[5] != SILO_FRAME_END || parser->bytes[4] != control_checksum(parser->bytes)) {
        return false;
    }

    const uint8_t raw_command = parser->bytes[1];
    if (raw_command < SILO_CMD_MOVE || raw_command > SILO_CMD_STOP_RELEASE) {
        return false;
    }

    const int8_t throttle = (int8_t)parser->bytes[2];
    const int8_t turn = (int8_t)parser->bytes[3];
    if (throttle < -100 || throttle > 100 || turn < -100 || turn > 100) {
        return false;
    }

    command->type = (SiloCommandType)raw_command;
    command->throttle = throttle;
    command->turn = turn;
    return true;
}

size_t silo_protocol_make_telemetry(uint8_t distance_1_mm,
                                    uint8_t distance_2_mm,
                                    uint8_t distance_3_mm,
                                    uint8_t flags,
                                    uint8_t output[SILO_TELEMETRY_FRAME_SIZE])
{
    output[0] = SILO_TELEMETRY_HEADER;
    output[1] = SILO_TELEMETRY_TYPE;
    output[2] = distance_1_mm;
    output[3] = distance_2_mm;
    output[4] = distance_3_mm;
    output[5] = flags;
    output[6] = (uint8_t)(output[1] ^ output[2] ^ output[3] ^ output[4] ^ output[5]);
    output[7] = SILO_FRAME_END;
    return SILO_TELEMETRY_FRAME_SIZE;
}
