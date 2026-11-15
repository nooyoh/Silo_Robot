#ifndef SILO_CONTROLLER_H
#define SILO_CONTROLLER_H

#include <stdbool.h>
#include <stdint.h>

#include "silo_protocol.h"

enum {
    SILO_COMMAND_TIMEOUT_MS = 300,
    SILO_PWM_MAX_PERMILLE = 1000,
    SILO_FLAG_STOP_LATCHED = 1u << 0,
    SILO_FLAG_TIMEOUT_HISTORY = 1u << 1
};

typedef struct {
    int16_t left_permille;
    int16_t right_permille;
} SiloMotorOutput;

typedef struct {
    SiloMotorOutput output;
    uint32_t last_valid_command_ms;
    bool has_received_command;
    bool stop_latched;
    bool timeout_history;
} SiloController;

void silo_controller_init(SiloController *controller, uint32_t now_ms);
void silo_controller_apply_command(SiloController *controller,
                                   const SiloCommand *command,
                                   uint32_t now_ms);
void silo_controller_tick(SiloController *controller, uint32_t now_ms);
uint8_t silo_controller_flags(const SiloController *controller);

#endif

