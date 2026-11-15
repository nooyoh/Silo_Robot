TARGET := silorobot-f401re
BUILD_DIR := build

PREFIX ?= arm-none-eabi-
CC := $(PREFIX)gcc
AS := $(PREFIX)gcc -x assembler-with-cpp
OBJCOPY := $(PREFIX)objcopy
SIZE := $(PREFIX)size

C_SOURCES := \
Core/Src/main.c Core/Src/stm32f4xx_it.c \
App/Src/silo_protocol.c App/Src/silo_controller.c App/Src/silo_motor_driver.c \
ThirdParty/CMSIS/Device/ST/STM32F4xx/Source/Templates/system_stm32f4xx.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_adc.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_adc_ex.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_cortex.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_dma.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_flash.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_flash_ex.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_gpio.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_pwr.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_pwr_ex.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_rcc.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_rcc_ex.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_tim.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_tim_ex.c \
ThirdParty/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_uart.c

ASM_SOURCES := ThirdParty/CMSIS/Device/ST/STM32F4xx/Source/Templates/gcc/startup_stm32f401xe.s

INCLUDES := -ICore/Inc -IApp/Inc \
-IThirdParty/CMSIS/Include \
-IThirdParty/CMSIS/Device/ST/STM32F4xx/Include \
-IThirdParty/STM32F4xx_HAL_Driver/Inc \
-IThirdParty/STM32F4xx_HAL_Driver/Inc/Legacy

CPU := -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
CFLAGS := $(CPU) -std=c11 -DUSE_HAL_DRIVER -DSTM32F401xE $(INCLUDES) \
-Wall -Wextra -Werror -Wno-unused-parameter -ffunction-sections -fdata-sections -Og -g3
LDFLAGS := $(CPU) -TSTM32F401RETX_FLASH.ld --specs=nano.specs --specs=nosys.specs \
-Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref -Wl,--gc-sections

OBJECTS := $(addprefix $(BUILD_DIR)/,$(C_SOURCES:.c=.o)) $(addprefix $(BUILD_DIR)/,$(ASM_SOURCES:.s=.o))

all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS) Makefile STM32F401RETX_FLASH.ld
	$(CC) $(OBJECTS) $(LDFLAGS) -o $@
	$(SIZE) $@

$(BUILD_DIR)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) -c $(CFLAGS) $< -o $@

$(BUILD_DIR)/%.o: %.s
	@mkdir -p $(dir $@)
	$(AS) -c $(CFLAGS) $< -o $@

$(BUILD_DIR)/%.hex: $(BUILD_DIR)/%.elf
	$(OBJCOPY) -O ihex $< $@

$(BUILD_DIR)/%.bin: $(BUILD_DIR)/%.elf
	$(OBJCOPY) -O binary -S $< $@

clean:
	rm -rf $(BUILD_DIR)

.NOTPARALLEL:
.PHONY: all clean
