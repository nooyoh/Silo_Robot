#include "silo_controller.h"

static int16_t clamp_axis(int16_t value)
{
    if (value > 100) {
        return 100;
    }
    if (value < -100) {
        return -100;
    }
    return value;
}

static void stop_motors(SiloController *controller)
{
    controller->output.left_permille = 0;
    controller->output.right_permille = 0;
}

static void apply_arcade_mix(SiloController *controller, int8_t throttle, int8_t turn)
{
    const int16_t left_percent = clamp_axis((int16_t)throttle + (int16_t)turn);
    const int16_t right_percent = clamp_axis((int16_t)throttle - (int16_t)turn);
    controller->output.left_permille = (int16_t)(left_percent * 10);
    controller->output.right_permille = (int16_t)(right_percent * 10);
}

void silo_controller_init(SiloController *controller, uint32_t now_ms)
{
    stop_motors(controller);
    controller->last_valid_command_ms = now_ms;
    controller->has_received_command = false;
    controller->stop_latched = true;
    controller->timeout_history = false;
}

void silo_controller_apply_command(SiloController *controller,
                                   const SiloCommand *command,
                                   uint32_t now_ms)
{
    controller->last_valid_command_ms = now_ms;
    controller->has_received_command = true;

    if (command->type == SILO_CMD_STOP) {
        controller->stop_latched = true;
        stop_motors(controller);
        return;
    }

    if (command->type == SILO_CMD_STOP_RELEASE) {
        controller->stop_latched = false;
        stop_motors(controller);
        return;
    }

    if (controller->stop_latched) {
        stop_motors(controller);
        return;
    }

    apply_arcade_mix(controller, command->throttle, command->turn);
}

void silo_controller_tick(SiloController *controller, uint32_t now_ms)
{
    if (!controller->has_received_command) {
        stop_motors(controller);
        return;
    }

    if ((uint32_t)(now_ms - controller->last_valid_command_ms) > SILO_COMMAND_TIMEOUT_MS) {
        controller->stop_latched = true;
        controller->timeout_history = true;
        stop_motors(controller);
    }
}

uint8_t silo_controller_flags(const SiloController *controller)
{
    uint8_t flags = 0;
    if (controller->stop_latched) {
        flags |= SILO_FLAG_STOP_LATCHED;
    }
    if (controller->timeout_history) {
        flags |= SILO_FLAG_TIMEOUT_HISTORY;
    }
    return flags;
}

