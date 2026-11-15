#ifndef MAIN_H
#define MAIN_H

#include "stm32f4xx_hal.h"

void Error_Handler(void);

#define M1_INA_Pin GPIO_PIN_8
#define M1_INA_GPIO_Port GPIOA
#define M1_INB_Pin GPIO_PIN_9
#define M1_INB_GPIO_Port GPIOA
#define M2_INA_Pin GPIO_PIN_10
#define M2_INA_GPIO_Port GPIOA
#define M2_INB_Pin GPIO_PIN_5
#define M2_INB_GPIO_Port GPIOB
#define M3_INA_Pin GPIO_PIN_5
#define M3_INA_GPIO_Port GPIOA
#define M3_INB_Pin GPIO_PIN_6
#define M3_INB_GPIO_Port GPIOA
#define M4_INA_Pin GPIO_PIN_7
#define M4_INA_GPIO_Port GPIOA
#define M4_INB_Pin GPIO_PIN_8
#define M4_INB_GPIO_Port GPIOB

#endif

