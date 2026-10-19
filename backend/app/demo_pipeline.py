from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from app.graph.event_bus import emit
from app.schemas.state import (
    ClockConfigRecord,
    DesignState,
    FeatureSpec,
    GeneratedFile,
    NodeMetric,
    PinAssignmentRecord,
    Requirements,
    RunMetrics,
    RunPlan,
    WireConnectionRecord,
)
from app.schemas.tools import ClockSource, PinFunction, WireColor
from app.simulate.runner import stream_simulation

DEMO_PROMPT = (
    "Read a DHT22 temperature and humidity sensor once per second and print "
    "the values over serial."
)

DEMO_CODE = r'''#include <stdio.h>
#include "pico/stdlib.h"

#define DHT_PIN 15
#define SAMPLE_INTERVAL_MS 1000

static bool wait_for_level(bool level, uint32_t timeout_us) {
    const uint64_t deadline = time_us_64() + timeout_us;
    while (gpio_get(DHT_PIN) != level) {
        if (time_us_64() >= deadline) return false;
    }
    return true;
}

static bool read_dht22(float *temperature, float *humidity) {
    uint8_t data[5] = {0};

    gpio_set_dir(DHT_PIN, GPIO_OUT);
    gpio_put(DHT_PIN, 0);
    sleep_ms(2);
    gpio_put(DHT_PIN, 1);
    sleep_us(30);
    gpio_set_dir(DHT_PIN, GPIO_IN);

    if (!wait_for_level(false, 100) || !wait_for_level(true, 100) ||
        !wait_for_level(false, 100)) return false;

    for (int bit = 0; bit < 40; ++bit) {
        if (!wait_for_level(true, 70)) return false;
        const uint64_t high_started = time_us_64();
        if (!wait_for_level(false, 100)) return false;
        data[bit / 8] <<= 1;
        if (time_us_64() - high_started > 45) data[bit / 8] |= 1;
    }

    if ((uint8_t)(data[0] + data[1] + data[2] + data[3]) != data[4]) return false;
    const uint16_t raw_humidity = ((uint16_t)data[0] << 8) | data[1];
    const uint16_t raw_temperature = ((uint16_t)(data[2] & 0x7f) << 8) | data[3];
    *humidity = raw_humidity / 10.0f;
    *temperature = raw_temperature / 10.0f;
    if (data[2] & 0x80) *temperature = -*temperature;
    return true;
}

int main(void) {
    stdio_init_all();
    gpio_init(DHT_PIN);
    gpio_pull_up(DHT_PIN);
    sleep_ms(1500);
    printf("[boot] Silo Labs DHT22 firmware\n");

    while (true) {
        float temperature = 0.0f;
        float humidity = 0.0f;
        if (read_dht22(&temperature, &humidity)) {
            printf("temperature=%.1f C humidity=%.1f %%\n", temperature, humidity);
        } else {
            printf("sensor_error=checksum_or_timeout\n");
        }
        sleep_ms(SAMPLE_INTERVAL_MS);
    }
}
'''

DEMO_CMAKE = '''cmake_minimum_required(VERSION 3.13)
include(pico_sdk_import.cmake)
project(dht22_serial C CXX ASM)
pico_sdk_init()
add_executable(dht22_serial main.c)
target_link_libraries(dht22_serial pico_stdlib)
pico_enable_stdio_usb(dht22_serial 1)
pico_enable_stdio_uart(dht22_serial 0)
pico_add_extra_outputs(dht22_serial)
'''

AGENT_PREPARATION_DELAY_SECONDS = 0.4
AGENT_ACTIVITY_DELAY_SECONDS = 0.55
CODE_CHARACTER_INTERVAL_SECONDS = 0.006
CODE_LINE_BREAK_PAUSE_SECONDS = 0.03

AgentAction = Callable[[DesignState], Awaitable[None]]


async def _run_agent(
    state: DesignState,
    agent: str,
    activities: list[tuple[str, str]],
    action: AgentAction,
    input_tokens: int,
    output_tokens: int,
) -> NodeMetric:
    state.active_agent = agent  # type: ignore[assignment]
    started_seconds = time.time()
    started_ms = int(started_seconds * 1000)
    emit({"type": "agent_start", "agent": agent, "timestamp": started_seconds})
    for key, label in activities:
        emit({"type": "agent_activity", "agent": agent, "key": key, "label": label, "status": "pending"})
    await asyncio.sleep(AGENT_PREPARATION_DELAY_SECONDS)
    for key, label in activities:
        emit({"type": "agent_activity", "agent": agent, "key": key, "label": label, "status": "active"})
        await asyncio.sleep(AGENT_ACTIVITY_DELAY_SECONDS)
        emit({"type": "agent_activity", "agent": agent, "key": key, "label": label, "status": "done"})
    await action(state)
    ended_ms = int(time.time() * 1000)
    duration_ms = max(1, ended_ms - started_ms)
    emit({"type": "agent_complete", "agent": agent, "duration_ms": duration_ms})
    state.active_agent = None
    metric = NodeMetric(
        node=agent,
        started_at_ms=started_ms,
        ended_at_ms=ended_ms,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    emit({"type": "metrics_update", "node": metric.model_dump()})
    return metric


async def run_demo_pipeline(session_id: str) -> DesignState:
    state = DesignState(session_id=session_id, user_prompt=DEMO_PROMPT)
    metrics = RunMetrics(run_id=session_id, started_at_ms=int(time.time() * 1000))

    async def supervisor(current: DesignState) -> None:
        feature = FeatureSpec(
            id="gpio-dht22-1",
            peripheral_family="GPIO",
            device_name="DHT22",
            intent="Sample temperature and humidity every second and print both over USB serial.",
        )
        current.run_plan = RunPlan(features=[feature], rationale="One sensor, one serial output, and a clear agent handoff path.")
        emit({"type": "run_plan", "features": [feature.model_dump()], "rationale": current.run_plan.rationale})

    async def requirements(current: DesignState) -> None:
        current.requirements = Requirements(
            peripheral_type="GPIO",
            device_name="DHT22",
            baud_rate=115200,
            description="Read DHT22 temperature and humidity once per second and print over serial.",
        )

    async def pinout(current: DesignState) -> None:
        pin = PinAssignmentRecord(
            pin_number=15,
            function=PinFunction.GPIO,
            peripheral_instance="GPIO",
            label="DHT22_DATA",
            wire_color="#e6c84a",
        )
        current.pin_assignments = [pin]
        emit({"type": "assign_pin", **pin.model_dump(mode="json")})

    async def peripheral(_: DesignState) -> None:
        return None

    async def wiring(current: DesignState) -> None:
        wires = [
            WireConnectionRecord(from_component="pico", from_pin="GP15", to_component="dht22", to_pin="SDA", color=WireColor.YELLOW),
            WireConnectionRecord(from_component="pico", from_pin="3V3", to_component="dht22", to_pin="VCC", color=WireColor.RED),
            WireConnectionRecord(from_component="pico", from_pin="GND.1", to_component="dht22", to_pin="GND", color=WireColor.BLACK),
        ]
        current.wires = wires
        for wire in wires:
            emit({"type": "add_wire", **wire.model_dump(mode="json")})
        current.wokwi_diagram = {
            "version": 1,
            "author": "Silo Labs",
            "editor": "wokwi",
            "parts": [
                {"type": "wokwi-pi-pico", "id": "pico", "top": 0, "left": 0, "attrs": {}},
                {"type": "wokwi-dht22", "id": "dht22", "top": 96, "left": 190, "attrs": {"temperature": "22.4", "humidity": "46.8"}},
            ],
            "connections": [[f"{wire.from_component}:{wire.from_pin}", f"{wire.to_component}:{wire.to_pin}", wire.color.value, []] for wire in wires],
        }
        emit({"type": "device_part_info", "device": "dht22", "wokwi_part": "wokwi-dht22", "is_stub": False, "note": ""})

    async def clocks(current: DesignState) -> None:
        clock = ClockConfigRecord(clock_domain=ClockSource.CLK_SYS, source=ClockSource.PLL_SYS, freq_hz=125_000_000, divider=1.0)
        current.clock_configs = [clock]
        emit({"type": "configure_clock", **clock.model_dump(mode="json")})

    async def verify(_: DesignState) -> None:
        return None

    async def compose(current: DesignState) -> None:
        files = [GeneratedFile(path="main.c", content=DEMO_CODE, language="c"), GeneratedFile(path="CMakeLists.txt", content=DEMO_CMAKE, language="cmake")]
        current.generated_files = files
        current.generated_code = DEMO_CODE
        current.cmake_content = DEMO_CMAKE
        for character in DEMO_CODE:
            emit({"type": "code_chunk", "delta": character})
            delay = CODE_LINE_BREAK_PAUSE_SECONDS if character == "\n" else CODE_CHARACTER_INTERVAL_SECONDS
            await asyncio.sleep(delay)
        emit({"type": "code_complete", "full_code": DEMO_CODE})
        emit({"type": "generated_files", "files": [file.model_dump() for file in files]})

    stages: list[tuple[str, list[tuple[str, str]], AgentAction, int, int]] = [
        ("supervisor", [("read", "Read the firmware request"), ("plan", "Publish the serial execution plan")], supervisor, 286, 92),
        ("requirements_parser", [("contract", "Extract the 1 second sample cadence"), ("serial", "Set USB serial output to 115200 baud")], requirements, 214, 76),
        ("pinout_resolver", [("datasheet", "Inspect the DHT22 data interface"), ("gpio", "Assign DATA to GP15 with pull-up")], pinout, 338, 84),
        ("peripheral_configurator", [("timing", "Set start pulse and bit timing windows"), ("checksum", "Configure timeout and checksum validation")], peripheral, 402, 118),
        ("wokwi_diagram_generator", [("part", "Place the native Wokwi DHT22 part"), ("wire", "Connect VCC, DATA, and ground")], wiring, 264, 105),
        ("clock_configurator", [("system", "Confirm the 125 MHz system clock"), ("delay", "Validate microsecond timing resolution")], clocks, 190, 64),
        ("errata_checker", [("electrical", "Check GPIO voltage and pull-up behavior"), ("review", "Verify timing margins and pin safety")], verify, 326, 96),
        ("code_composer", [("driver", "Write the DHT22 pulse decoder"), ("loop", "Add the 1 second serial sample loop")], compose, 612, 486),
    ]

    for agent, activities, action, input_tokens, output_tokens in stages:
        metric = await _run_agent(state, agent, activities, action, input_tokens, output_tokens)
        metrics.nodes.append(metric)
        metrics.total_input_tokens += input_tokens
        metrics.total_output_tokens += output_tokens

    emit({"type": "build_start"})
    build_lines = [
        "Configuring Pico SDK project",
        "Compiling main.c",
        "Linking dht22_serial.elf",
        "Firmware validation passed",
    ]
    for line in build_lines:
        emit({"type": "build_log", "line": line})
        await asyncio.sleep(0.16)
    state.build_stdout = "\n".join(build_lines)
    state.build_success = True

    emit({"type": "simulate_start"})
    simulation_lines: list[str] = []
    async for line in stream_simulation(None, state.wokwi_diagram):
        simulation_lines.append(line)
        emit({"type": "simulate_output", "line": line})
    state.simulate_log = "\n".join(simulation_lines)
    state.pipeline_complete = True

    metrics.ended_at_ms = int(time.time() * 1000)
    metrics.total_cost_usd = 0.0
    state.metrics = metrics
    emit({"type": "metrics_summary", "metrics": metrics.model_dump()})
    return state
