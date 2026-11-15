#include "main.h"

#include "silo_controller.h"
#include "silo_motor_driver.h"
#include "silo_protocol.h"

ADC_HandleTypeDef hadc1;
TIM_HandleTypeDef htim2;
TIM_HandleTypeDef htim3;
TIM_HandleTypeDef htim4;
UART_HandleTypeDef huart2;

static SiloController controller;
static SiloProtocolParser parser;
static uint8_t uart_rx_byte;
static SiloMotorOutput applied_output;

static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_ADC1_Init(void);
static void MX_TIM2_Init(void);
static void MX_TIM3_Init(void);
static void MX_TIM4_Init(void);
static void MX_USART2_UART_Init(void);
static void start_outputs(void);
static void apply_motor_outputs(void);
static uint16_t read_adc_channel(uint32_t channel);
static uint8_t distance_mm_unavailable(uint16_t raw_adc);
static void send_telemetry(void);
void HAL_TIM_MspPostInit(TIM_HandleTypeDef *timer);

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_ADC1_Init();
    MX_TIM2_Init();
    MX_TIM3_Init();
    MX_TIM4_Init();
    MX_USART2_UART_Init();

    silo_protocol_init(&parser);
    silo_controller_init(&controller, HAL_GetTick());
    start_outputs();
    apply_motor_outputs();
    HAL_UART_Receive_IT(&huart2, &uart_rx_byte, 1);

    uint32_t last_motor_update_ms = HAL_GetTick();
    uint32_t last_telemetry_ms = HAL_GetTick();
    while (1) {
        const uint32_t now_ms = HAL_GetTick();
        silo_controller_tick(&controller, now_ms);

        if ((uint32_t)(now_ms - last_motor_update_ms) >= 1u) {
            last_motor_update_ms = now_ms;
            if (controller.stop_latched) {
                applied_output.left_permille = 0;
                applied_output.right_permille = 0;
            } else {
                applied_output.left_permille = silo_motor_slew_step(
                    applied_output.left_permille, controller.output.left_permille, 10u);
                applied_output.right_permille = silo_motor_slew_step(
                    applied_output.right_permille, controller.output.right_permille, 10u);
            }
            apply_motor_outputs();
        }

        if ((uint32_t)(now_ms - last_telemetry_ms) >= 50u) {
            last_telemetry_ms = now_ms;
            send_telemetry();
        }
    }
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2) {
        SiloCommand command;
        if (silo_protocol_push_byte(&parser, uart_rx_byte, &command)) {
            silo_controller_apply_command(&controller, &command, HAL_GetTick());
        }
        HAL_UART_Receive_IT(&huart2, &uart_rx_byte, 1);
    }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2) {
        HAL_UART_Receive_IT(&huart2, &uart_rx_byte, 1);
    }
}

static void write_motor(const SiloMotorSignal *signal,
                        GPIO_TypeDef *ina_port, uint16_t ina_pin,
                        GPIO_TypeDef *inb_port, uint16_t inb_pin,
                        TIM_HandleTypeDef *timer, uint32_t channel)
{
    __HAL_TIM_SET_COMPARE(timer, channel, 0u);
    HAL_GPIO_WritePin(ina_port, ina_pin, signal->ina ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(inb_port, inb_pin, signal->inb ? GPIO_PIN_SET : GPIO_PIN_RESET);
    __HAL_TIM_SET_COMPARE(timer, channel, (uint32_t)signal->pwm_permille * 42u / 10u);
}

static void apply_motor_outputs(void)
{
    const SiloDriverSignals signals = silo_motor_driver_expand_tracks(&applied_output);
    write_motor(&signals.motor[0], M1_INA_GPIO_Port, M1_INA_Pin, M1_INB_GPIO_Port, M1_INB_Pin,
                &htim3, TIM_CHANNEL_1);
    write_motor(&signals.motor[1], M2_INA_GPIO_Port, M2_INA_Pin, M2_INB_GPIO_Port, M2_INB_Pin,
                &htim3, TIM_CHANNEL_2);
    write_motor(&signals.motor[2], M3_INA_GPIO_Port, M3_INA_Pin, M3_INB_GPIO_Port, M3_INB_Pin,
                &htim4, TIM_CHANNEL_1);
    write_motor(&signals.motor[3], M4_INA_GPIO_Port, M4_INA_Pin, M4_INB_GPIO_Port, M4_INB_Pin,
                &htim2, TIM_CHANNEL_3);
}

static void start_outputs(void)
{
    if (HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_3) != HAL_OK ||
        HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1) != HAL_OK ||
        HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_2) != HAL_OK ||
        HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_1) != HAL_OK) {
        Error_Handler();
    }
}

static uint16_t read_adc_channel(uint32_t channel)
{
    ADC_ChannelConfTypeDef config = {0};
    config.Channel = channel;
    config.Rank = 1;
    config.SamplingTime = ADC_SAMPLETIME_84CYCLES;
    if (HAL_ADC_ConfigChannel(&hadc1, &config) != HAL_OK || HAL_ADC_Start(&hadc1) != HAL_OK) {
        return 0;
    }
    if (HAL_ADC_PollForConversion(&hadc1, 2) != HAL_OK) {
        HAL_ADC_Stop(&hadc1);
        return 0;
    }
    const uint16_t value = (uint16_t)HAL_ADC_GetValue(&hadc1);
    HAL_ADC_Stop(&hadc1);
    return value;
}

static uint8_t distance_mm_unavailable(uint16_t raw_adc)
{
    (void)raw_adc;
    return 0; /* 0 means unavailable until GP2Y0A51SK0F calibration is measured. */
}

static void send_telemetry(void)
{
    uint8_t frame[SILO_TELEMETRY_FRAME_SIZE];
    const uint8_t d1 = distance_mm_unavailable(read_adc_channel(ADC_CHANNEL_0));
    const uint8_t d2 = distance_mm_unavailable(read_adc_channel(ADC_CHANNEL_1));
    const uint8_t d3 = distance_mm_unavailable(read_adc_channel(ADC_CHANNEL_4));
    silo_protocol_make_telemetry(d1, d2, d3, silo_controller_flags(&controller), frame);
    HAL_UART_Transmit(&huart2, frame, sizeof(frame), 5);
}

static void timer_pwm_init(TIM_HandleTypeDef *timer, TIM_TypeDef *instance)
{
    TIM_OC_InitTypeDef channel = {0};
    timer->Instance = instance;
    timer->Init.Prescaler = 0;
    timer->Init.CounterMode = TIM_COUNTERMODE_UP;
    timer->Init.Period = 4199;
    timer->Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    timer->Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    if (HAL_TIM_PWM_Init(timer) != HAL_OK) {
        Error_Handler();
    }
    channel.OCMode = TIM_OCMODE_PWM1;
    channel.Pulse = 0;
    channel.OCPolarity = TIM_OCPOLARITY_HIGH;
    channel.OCFastMode = TIM_OCFAST_DISABLE;
    if (instance == TIM3) {
        if (HAL_TIM_PWM_ConfigChannel(timer, &channel, TIM_CHANNEL_1) != HAL_OK ||
            HAL_TIM_PWM_ConfigChannel(timer, &channel, TIM_CHANNEL_2) != HAL_OK) {
            Error_Handler();
        }
    } else if (instance == TIM2) {
        if (HAL_TIM_PWM_ConfigChannel(timer, &channel, TIM_CHANNEL_3) != HAL_OK) Error_Handler();
    } else {
        if (HAL_TIM_PWM_ConfigChannel(timer, &channel, TIM_CHANNEL_1) != HAL_OK) Error_Handler();
    }
    HAL_TIM_MspPostInit(timer);
}

static void MX_TIM2_Init(void) { timer_pwm_init(&htim2, TIM2); }
static void MX_TIM3_Init(void) { timer_pwm_init(&htim3, TIM3); }
static void MX_TIM4_Init(void) { timer_pwm_init(&htim4, TIM4); }

static void MX_ADC1_Init(void)
{
    hadc1.Instance = ADC1;
    hadc1.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
    hadc1.Init.Resolution = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode = DISABLE;
    hadc1.Init.ContinuousConvMode = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion = 1;
    hadc1.Init.DMAContinuousRequests = DISABLE;
    hadc1.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
    if (HAL_ADC_Init(&hadc1) != HAL_OK) Error_Handler();
}

static void MX_USART2_UART_Init(void)
{
    huart2.Instance = USART2;
    huart2.Init.BaudRate = 115200;
    huart2.Init.WordLength = UART_WORDLENGTH_8B;
    huart2.Init.StopBits = UART_STOPBITS_1;
    huart2.Init.Parity = UART_PARITY_NONE;
    huart2.Init.Mode = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart2) != HAL_OK) Error_Handler();
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef gpio = {0};
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    HAL_GPIO_WritePin(GPIOA, M1_INA_Pin | M1_INB_Pin | M2_INA_Pin | M3_INA_Pin | M3_INB_Pin | M4_INA_Pin,
                      GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB, M2_INB_Pin | M4_INB_Pin, GPIO_PIN_RESET);
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    gpio.Pin = M1_INA_Pin | M1_INB_Pin | M2_INA_Pin | M3_INA_Pin | M3_INB_Pin | M4_INA_Pin;
    HAL_GPIO_Init(GPIOA, &gpio);
    gpio.Pin = M2_INB_Pin | M4_INB_Pin;
    HAL_GPIO_Init(GPIOB, &gpio);
}

void HAL_ADC_MspInit(ADC_HandleTypeDef *adc)
{
    if (adc->Instance == ADC1) {
        GPIO_InitTypeDef gpio = {0};
        __HAL_RCC_ADC1_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();
        gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_4;
        gpio.Mode = GPIO_MODE_ANALOG;
        gpio.Pull = GPIO_NOPULL;
        HAL_GPIO_Init(GPIOA, &gpio);
    }
}

void HAL_TIM_PWM_MspInit(TIM_HandleTypeDef *timer)
{
    if (timer->Instance == TIM2) __HAL_RCC_TIM2_CLK_ENABLE();
    if (timer->Instance == TIM3) __HAL_RCC_TIM3_CLK_ENABLE();
    if (timer->Instance == TIM4) __HAL_RCC_TIM4_CLK_ENABLE();
}

void HAL_TIM_MspPostInit(TIM_HandleTypeDef *timer)
{
    GPIO_InitTypeDef gpio = {0};
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    if (timer->Instance == TIM2) {
        __HAL_RCC_GPIOB_CLK_ENABLE();
        gpio.Pin = GPIO_PIN_10;
        gpio.Alternate = GPIO_AF1_TIM2;
        HAL_GPIO_Init(GPIOB, &gpio);
    } else if (timer->Instance == TIM3) {
        __HAL_RCC_GPIOB_CLK_ENABLE();
        __HAL_RCC_GPIOC_CLK_ENABLE();
        gpio.Pin = GPIO_PIN_4;
        gpio.Alternate = GPIO_AF2_TIM3;
        HAL_GPIO_Init(GPIOB, &gpio);
        gpio.Pin = GPIO_PIN_7;
        HAL_GPIO_Init(GPIOC, &gpio);
    } else if (timer->Instance == TIM4) {
        __HAL_RCC_GPIOB_CLK_ENABLE();
        gpio.Pin = GPIO_PIN_6;
        gpio.Alternate = GPIO_AF2_TIM4;
        HAL_GPIO_Init(GPIOB, &gpio);
    }
}

void HAL_UART_MspInit(UART_HandleTypeDef *uart)
{
    if (uart->Instance == USART2) {
        GPIO_InitTypeDef gpio = {0};
        __HAL_RCC_USART2_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();
        gpio.Pin = GPIO_PIN_2 | GPIO_PIN_3;
        gpio.Mode = GPIO_MODE_AF_PP;
        gpio.Pull = GPIO_NOPULL;
        gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
        gpio.Alternate = GPIO_AF7_USART2;
        HAL_GPIO_Init(GPIOA, &gpio);
        HAL_NVIC_SetPriority(USART2_IRQn, 5, 0);
        HAL_NVIC_EnableIRQ(USART2_IRQn);
    }
}

static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    osc.HSIState = RCC_HSI_ON;
    osc.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSI;
    osc.PLL.PLLM = 16;
    osc.PLL.PLLN = 336;
    osc.PLL.PLLP = RCC_PLLP_DIV4;
    osc.PLL.PLLQ = 7;
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) Error_Handler();
    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV2;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_2) != HAL_OK) Error_Handler();
}

void Error_Handler(void)
{
    __disable_irq();
    HAL_GPIO_WritePin(GPIOA, M1_INA_Pin | M1_INB_Pin | M2_INA_Pin | M3_INA_Pin | M3_INB_Pin | M4_INA_Pin,
                      GPIO_PIN_RESET);
    HAL_GPIO_WritePin(GPIOB, M2_INB_Pin | M4_INB_Pin, GPIO_PIN_RESET);
    while (1) {}
}
