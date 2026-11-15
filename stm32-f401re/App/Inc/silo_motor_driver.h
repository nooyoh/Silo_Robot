#ifndef SILO_MOTOR_DRIVER_H
#define SILO_MOTOR_DRIVER_H

#include <stdbool.h>
#include <stdint.h>

#include "silo_controller.h"

typedef struct {
    uint16_t pwm_permille;
    bool ina;
    bool inb;
} SiloMotorSignal;

typedef struct {
    SiloMotorSignal motor[4];
} SiloDriverSignals;

SiloMotorSignal silo_motor_signal_from_signed_pwm(int16_t signed_permille);
SiloDriverSignals silo_motor_driver_expand_tracks(const SiloMotorOutput *tracks);
int16_t silo_motor_slew_step(int16_t current, int16_t target, uint16_t max_step);

#endif
