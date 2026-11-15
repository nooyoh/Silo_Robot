/* Exposes the real STM32 firmware logic to the Python verification harness, so the
   off-robot tests exercise the same mixing and framing the board runs rather than a
   reimplementation that could drift from it. Built by tools/verify/run.py. */

#if defined(_WIN32)
#define SILO_EXPORT __declspec(dllexport)
#else
#define SILO_EXPORT __attribute__((visibility("default")))
#endif

#include "silo_controller.h"
#include "silo_motor_driver.h"
#include "silo_protocol.h"

/* Axis commands -> signed left/right permille, straight through the firmware's own
   controller and deadzone mapping. Sign carries the direction bits. */
SILO_EXPORT
void silo_mix(int throttle, int turn, int *left_out, int *right_out)
{
    SiloController controller;
    silo_controller_init(&controller, 0u);

    SiloCommand release = { SILO_CMD_STOP_RELEASE, 0, 0 };
    silo_controller_apply_command(&controller, &release, 0u);

    SiloCommand move;
    move.type = SILO_CMD_MOVE;
    move.throttle = (int8_t)throttle;
    move.turn = (int8_t)turn;
    silo_controller_apply_command(&controller, &move, 0u);

    SiloDriverSignals signals = silo_motor_driver_expand_tracks(&controller.output);
    /* motor[0] = left front, motor[2] = right front; ina set means reverse. */
    *left_out = (int)signals.motor[0].pwm_permille * (signals.motor[0].ina ? -1 : 1);
    *right_out = (int)signals.motor[2].pwm_permille * (signals.motor[2].ina ? -1 : 1);
}

/* Feed bytes exactly as they arrive on the wire; returns 1 once the firmware parser
   accepts a frame, so the Nano's framing can be checked against the real decoder. */
SILO_EXPORT
int silo_parse_frame(const unsigned char *bytes, int length,
                     int *type_out, int *throttle_out, int *turn_out)
{
    SiloProtocolParser parser;
    SiloCommand command;
    int accepted = 0;
    int index;

    silo_protocol_init(&parser);
    for (index = 0; index < length; ++index) {
        if (silo_protocol_push_byte(&parser, bytes[index], &command)) {
            *type_out = (int)command.type;
            *throttle_out = command.throttle;
            *turn_out = command.turn;
            accepted = 1;
        }
    }
    return accepted;
}

/* Build the uplink frames the firmware sends, so the Nano-side parser is tested against
   real firmware output instead of a hand-written imitation of it. */
SILO_EXPORT
int silo_make_telemetry(int d1, int d2, int d3, int flags, unsigned char *out)
{
    return (int)silo_protocol_make_telemetry((uint8_t)d1, (uint8_t)d2, (uint8_t)d3,
                                             (uint8_t)flags, out);
}

SILO_EXPORT
int silo_make_encoder(int left, int right, int flags, unsigned char *out)
{
    return (int)silo_protocol_make_encoder_telemetry((int32_t)left, (int32_t)right,
                                                     (uint8_t)flags, out);
}

SILO_EXPORT
int silo_make_battery(int pack_1_mv, int pack_2_mv, int flags, unsigned char *out)
{
    return (int)silo_protocol_make_battery_telemetry(
        (uint16_t)pack_1_mv, (uint16_t)pack_2_mv, (uint8_t)flags, out);
}
