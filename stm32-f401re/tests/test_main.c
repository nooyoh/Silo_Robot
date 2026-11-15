#include <assert.h>
#include <stdio.h>

#include "silo_controller.h"
#include "silo_motor_driver.h"
#include "silo_protocol.h"

static SiloCommand parse_frame(const uint8_t *frame)
{
    SiloProtocolParser parser;
    SiloCommand command = {0};
    bool complete = false;
    silo_protocol_init(&parser);
    for (size_t i = 0; i < SILO_CONTROL_FRAME_SIZE; ++i) {
        complete = silo_protocol_push_byte(&parser, frame[i], &command);
    }
    assert(complete);
    return command;
}

static void test_known_nano_frame(void)
{
    const uint8_t frame[] = {0xAA, 0x01, 0x9C, 0x32, 0xAF, 0x55};
    const SiloCommand command = parse_frame(frame);
    assert(command.type == SILO_CMD_MOVE);
    assert(command.throttle == -100);
    assert(command.turn == 50);
}

static void test_parser_rejects_bad_checksum(void)
{
    const uint8_t frame[] = {0xAA, 0x01, 10, 20, 0x00, 0x55};
    SiloProtocolParser parser;
    SiloCommand command;
    bool complete = false;
    silo_protocol_init(&parser);
    for (size_t i = 0; i < sizeof(frame); ++i) {
        complete = silo_protocol_push_byte(&parser, frame[i], &command);
    }
    assert(!complete);
}

static void test_header_value_is_valid_signed_axis_data(void)
{
    const uint8_t frame[] = {0xAA, 0x01, 0xAA, 0x00, 0xAB, 0x55};
    const SiloCommand command = parse_frame(frame);
    assert(command.throttle == -86);
    assert(command.turn == 0);
}

static void test_stop_release_mix_and_timeout(void)
{
    SiloController controller;
    silo_controller_init(&controller, 0);
    assert(controller.stop_latched);

    SiloCommand move = {SILO_CMD_MOVE, 40, 10};
    silo_controller_apply_command(&controller, &move, 10);
    assert(controller.output.left_permille == 0);

    SiloCommand release = {SILO_CMD_STOP_RELEASE, 0, 0};
    silo_controller_apply_command(&controller, &release, 20);
    silo_controller_apply_command(&controller, &move, 30);
    assert(controller.output.left_permille == 500);
    assert(controller.output.right_permille == 300);

    silo_controller_tick(&controller, 330);
    assert(controller.output.left_permille == 500);
    silo_controller_tick(&controller, 331);
    assert(controller.stop_latched);
    assert(controller.timeout_history);
    assert(controller.output.left_permille == 0);
    assert(controller.output.right_permille == 0);
}

static void test_mix_clamps(void)
{
    SiloController controller;
    silo_controller_init(&controller, 0);
    SiloCommand release = {SILO_CMD_STOP_RELEASE, 0, 0};
    SiloCommand move = {SILO_CMD_MOVE, 100, 100};
    silo_controller_apply_command(&controller, &release, 0);
    silo_controller_apply_command(&controller, &move, 1);
    assert(controller.output.left_permille == 1000);
    assert(controller.output.right_permille == 0);
}

static void test_telemetry(void)
{
    uint8_t frame[SILO_TELEMETRY_FRAME_SIZE];
    assert(silo_protocol_make_telemetry(20, 80, 150, 3, frame) == sizeof(frame));
    assert(frame[0] == 0xBB);
    assert(frame[1] == 0x01);
    assert(frame[6] == (uint8_t)(0x01 ^ 20 ^ 80 ^ 150 ^ 3));
    assert(frame[7] == 0x55);
}

static void test_motor_driver_signals(void)
{
    const SiloMotorOutput tracks = {-750, 250};
    const SiloDriverSignals signals = silo_motor_driver_expand_tracks(&tracks);
    assert(signals.motor[0].pwm_permille == 750);
    assert(signals.motor[0].ina && !signals.motor[0].inb);
    assert(signals.motor[1].pwm_permille == 750);
    assert(signals.motor[2].pwm_permille == 250);
    assert(!signals.motor[2].ina && signals.motor[2].inb);
    assert(signals.motor[3].pwm_permille == 250);

    const SiloMotorSignal stopped = silo_motor_signal_from_signed_pwm(0);
    assert(stopped.pwm_permille == 0);
    assert(!stopped.ina && !stopped.inb);
}

static void test_motor_slew_crosses_zero_before_reversing(void)
{
    int16_t value = 30;
    value = silo_motor_slew_step(value, -100, 10);
    assert(value == 20);
    value = silo_motor_slew_step(value, -100, 10);
    assert(value == 10);
    value = silo_motor_slew_step(value, -100, 10);
    assert(value == 0);
    value = silo_motor_slew_step(value, -100, 10);
    assert(value == -10);
}

int main(void)
{
    test_known_nano_frame();
    test_parser_rejects_bad_checksum();
    test_header_value_is_valid_signed_axis_data();
    test_stop_release_mix_and_timeout();
    test_mix_clamps();
    test_telemetry();
    test_motor_driver_signals();
    test_motor_slew_crosses_zero_before_reversing();
    puts("All STM32 core tests passed.");
    return 0;
}
