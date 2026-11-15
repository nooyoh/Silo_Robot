#include "silo_motor_driver.h"

SiloMotorSignal silo_motor_signal_from_signed_pwm(int16_t signed_permille)
{
    SiloMotorSignal signal = {0, false, false};

    if (signed_permille > 0) {
        signal.pwm_permille = (uint16_t)signed_permille;
        signal.ina = false;
        signal.inb = true;
    } else if (signed_permille < 0) {
        signal.pwm_permille = (uint16_t)(-signed_permille);
        signal.ina = true;
        signal.inb = false;
    }

    if (signal.pwm_permille > SILO_PWM_MAX_PERMILLE) {
        signal.pwm_permille = SILO_PWM_MAX_PERMILLE;
    }
    return signal;
}

SiloDriverSignals silo_motor_driver_expand_tracks(const SiloMotorOutput *tracks)
{
    SiloDriverSignals signals;
    const SiloMotorSignal left = silo_motor_signal_from_signed_pwm(tracks->left_permille);
    const SiloMotorSignal right = silo_motor_signal_from_signed_pwm(tracks->right_permille);

    signals.motor[0] = left;
    signals.motor[1] = left;
    signals.motor[2] = right;
    signals.motor[3] = right;
    return signals;
}

int16_t silo_motor_slew_step(int16_t current, int16_t target, uint16_t max_step)
{
    int16_t safe_target = target;
    if ((current > 0 && target < 0) || (current < 0 && target > 0)) {
        safe_target = 0;
    }

    if (current < safe_target) {
        const int16_t delta = (int16_t)(safe_target - current);
        return (delta > (int16_t)max_step) ? (int16_t)(current + max_step) : safe_target;
    }
    if (current > safe_target) {
        const int16_t delta = (int16_t)(current - safe_target);
        return (delta > (int16_t)max_step) ? (int16_t)(current - max_step) : safe_target;
    }
    return current;
}
