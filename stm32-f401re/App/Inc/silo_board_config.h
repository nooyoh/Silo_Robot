#ifndef SILO_BOARD_CONFIG_H
#define SILO_BOARD_CONFIG_H

/*
 * First-pass NUCLEO-F401RE pin assignment.
 * Keep this file synchronized with the CubeMX .ioc configuration.
 */

#define SILO_UART_INSTANCE USART2
#define SILO_UART_BAUD_RATE 115200u
#define SILO_PWM_FREQUENCY_HZ 20000u

/* ADC: distance sensors 1..3 */
#define SILO_DISTANCE_1_PIN PA0_ADC1_IN0
#define SILO_DISTANCE_2_PIN PA1_ADC1_IN1
#define SILO_DISTANCE_3_PIN PA4_ADC1_IN4

/* PWM channels */
#define SILO_M1_PWM_PIN PB4_TIM3_CH1
#define SILO_M2_PWM_PIN PC7_TIM3_CH2
#define SILO_M3_PWM_PIN PB6_TIM4_CH1
#define SILO_M4_PWM_PIN PB10_TIM2_CH3

/* DFR0601 direction inputs */
#define SILO_M1_INA_PIN PA8_GPIO
#define SILO_M1_INB_PIN PA9_GPIO
#define SILO_M2_INA_PIN PA10_GPIO
#define SILO_M2_INB_PIN PB5_GPIO
#define SILO_M3_INA_PIN PA5_GPIO
#define SILO_M3_INB_PIN PA6_GPIO
#define SILO_M4_INA_PIN PA7_GPIO
#define SILO_M4_INB_PIN PB8_GPIO

#endif

