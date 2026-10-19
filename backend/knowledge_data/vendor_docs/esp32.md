# ESP32 vendor notes

## GPIO overview
The ESP32 has GPIO0..GPIO39 (GPIO20, 24 and 28..31 do not exist). GPIO34..GPIO39 are input-only and have no internal pull-up or pull-down. GPIO6..GPIO11 are wired to the SPI flash on modules and must never be used. Strapping pins GPIO0, GPIO2, GPIO5, GPIO12 (MTDI, selects flash voltage) and GPIO15 are sampled at reset; avoid loading them with pull-downs or pull-ups that change boot mode. GPIO1/GPIO3 are UART0 TX/RX used by the console and bootloader.

## GPIO matrix and IO_MUX
Most peripheral signals route through the GPIO matrix, so I2C, UART, LEDC and RMT can use almost any output-capable GPIO. IO_MUX direct paths exist for the fastest SPI and for UART0. Matrix routing is configured with GPIO_FUNCx_OUT_SEL_CFG and GPIO_FUNCy_IN_SEL_CFG; ESP-IDF drivers do this for you.

## Default peripheral pins
I2C: SDA GPIO21, SCL GPIO22 (Arduino and DevKit convention). VSPI (SPI3): MOSI GPIO23, MISO GPIO19, SCLK GPIO18, CS GPIO5. HSPI (SPI2): MOSI GPIO13, MISO GPIO12, SCLK GPIO14, CS GPIO15. UART2: TX GPIO17, RX GPIO16. The DevKitC on Wokwi names pins by number ("21", "22") plus "3V3", "5V" and "GND.1".."GND.3".

## ADC
ADC1 channels: GPIO36 (CH0), GPIO37 (CH1), GPIO38 (CH2), GPIO39 (CH3), GPIO32 (CH4), GPIO33 (CH5), GPIO34 (CH6), GPIO35 (CH7). ADC2 (GPIO0, 2, 4, 12..15, 25..27) cannot be used while Wi-Fi is running. The ADC is 12-bit and non-linear near the rails; use attenuation ADC_ATTEN_DB_12 for a 0..3.1 V range and the esp_adc calibration scheme.

## PWM and LED strips
PWM uses the LEDC peripheral: 16 channels, 8 timers. ledc_timer_config sets frequency and resolution (for example 50 Hz at 14-bit for servos), ledc_channel_config binds a GPIO, ledc_set_duty + ledc_update_duty change duty. WS2812/NeoPixel strips are driven by the RMT peripheral (led_strip component) rather than bit-banging.

## Clock tree
The ESP32 uses a 40 MHz crystal (XTAL). The PLL produces 320 MHz or 480 MHz; the CPU runs at 80, 160 or 240 MHz (CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ). APB_CLK is 80 MHz and clocks UART, I2C, SPI and LEDC. RTC_SLOW_CLK is the 150 kHz internal RC or a 32 kHz crystal. ESP-IDF's bootloader and esp_clk_init configure clocks before app_main().

## ESP-IDF idioms
Entry point is void app_main(void) in main/main.c. The project needs a top-level CMakeLists.txt (cmake_minimum_required, include($ENV{IDF_PATH}/tools/cmake/project.cmake), project(firmware)) and main/CMakeLists.txt with idf_component_register(SRCS "main.c" INCLUDE_DIRS "."). I2C master (IDF 5.2+): i2c_new_master_bus with i2c_master_bus_config_t {.sda_io_num=21, .scl_io_num=22, .flags.enable_internal_pullup=true}, then i2c_master_bus_add_device and i2c_master_transmit_receive. Delays: vTaskDelay(pdMS_TO_TICKS(1000)); microsecond waits use esp_rom_delay_us. printf goes to UART0 at 115200 baud. Single-wire sensors like DHT22 need interrupts disabled (portDISABLE_INTERRUPTS or a critical section) around the 40-bit read.

## Known pitfalls
ESP32 errata 3.11: when certain RTC peripherals (SARADC1, SARADC2, AMP, HALL) are powered up, GPIO36 and GPIO39 inputs are pulled down for about 80 ns; avoid using them as interrupt sources while sampling ADC. Revision v1.0 silicon has a cache bug requiring the CONFIG_ESP32_REV_MIN workaround with PSRAM. Writing to GPIO6..11 crashes the chip by corrupting flash access.
