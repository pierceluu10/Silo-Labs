from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents.code_composer import is_core_file, split_main_and_cmake
from app.agents.wokwi_diagram_generator import _render_diagram_json
from app.graph.pipeline import _route_after_build
from app.knowledge.graph import UnknownPeripheralError, get_graph, reset_target_mcu, set_target_mcu
from app.main import app
from app.mcu import get_profile, list_profiles
from app.schemas.state import DesignState, GeneratedFile
from app.schemas.tools import AddWire, AssignPin, ConfigureClock, PinFunction, SetRegister, WireColor

STM32_I2C1_BASE = 0x40005400


@pytest.fixture
def target(request: pytest.FixtureRequest) -> Iterator[str]:
    token = set_target_mcu(request.param)
    yield request.param
    reset_target_mcu(token)


def _pin(n: int) -> AssignPin:
    return AssignPin(
        pin_number=n,
        function=PinFunction.I2C_SDA,
        peripheral_instance="I2C1",
        label="SDA",
        wire_color="#e6c84a",
    )


def test_every_profile_has_svd_and_board_part() -> None:
    assert list_profiles() == ["esp32", "rp2040", "stm32f103"]
    for name in list_profiles():
        profile = get_profile(name)
        graph = get_graph(name)
        assert graph.list_peripherals(), name
        assert graph.get_wokwi_component(profile.board_part), name
        for core in profile.core_peripherals:
            assert core in graph.list_peripherals(), f"{name}: core peripheral {core} not in SVD"


def test_register_counts_exceed_one_thousand_across_mcus() -> None:
    total = sum(
        len(get_graph(name)._peripherals[pe].registers)
        for name in list_profiles()
        for pe in get_graph(name).list_peripherals()
    )
    print(f"indexed registers across MCUs: {total}")
    assert total > 1000


@pytest.mark.parametrize("target", ["stm32f103"], indirect=True)
def test_set_register_resolves_against_target_svd(target: str) -> None:
    write = SetRegister(
        peripheral="I2C1", register="CR1", field_name="PE", value=1,
        bit_offset=0, bit_width=1, human_explanation="enable",
    )
    assert write.address == STM32_I2C1_BASE
    with pytest.raises(UnknownPeripheralError):
        SetRegister(
            peripheral="I2C0", register="IC_CON", field_name="SPEED", value=2,
            bit_offset=0, bit_width=1, human_explanation="rp2040-only register",
        )


@pytest.mark.parametrize(
    ("target", "pin_number", "expected"),
    [("rp2040", 4, "GP4"), ("stm32f103", 22, "PB6"), ("stm32f103", 45, "PC13"), ("esp32", 21, "GPIO21")],
    indirect=["target"],
)
def test_pin_name_derived_per_mcu(target: str, pin_number: int, expected: str) -> None:
    assert _pin(pin_number).pin_name == expected


@pytest.mark.parametrize(("target", "out_of_range"), [("rp2040", 30), ("esp32", 40), ("stm32f103", 48)], indirect=["target"])
def test_pin_number_bounded_by_target(target: str, out_of_range: int) -> None:
    with pytest.raises(ValidationError):
        _pin(out_of_range)


@pytest.mark.parametrize("target", ["stm32f103"], indirect=True)
def test_clock_domains_validated_per_mcu(target: str) -> None:
    pll = ConfigureClock(clock_domain="pll", source="HSE", freq_hz=72_000_000, divider=1.0, pll_vco_freq_hz=72_000_000)
    assert pll.clock_domain == "PLL"
    with pytest.raises(ValidationError):
        ConfigureClock(clock_domain="CLK_SYS", source="PLL_SYS", freq_hz=125_000_000, divider=1.0)
    with pytest.raises(ValidationError):
        ConfigureClock(clock_domain="PLL", source="HSE", freq_hz=72_000_000, divider=1.0)


def test_esp_idf_layout_entry_point_detected() -> None:
    files = [
        GeneratedFile(path="CMakeLists.txt", content="project(firmware)"),
        GeneratedFile(path="main/CMakeLists.txt", content="idf_component_register()"),
        GeneratedFile(path="main/main.c", content="void app_main(void) {}"),
    ]
    assert split_main_and_cmake(files) == ("void app_main(void) {}", "project(firmware)")
    assert [f.path for f in files if not is_core_file(f.path)] == ["main/CMakeLists.txt"]


@pytest.mark.parametrize("target", ["esp32"], indirect=True)
def test_diagram_uses_profile_board_and_numbered_ground(target: str) -> None:
    board = get_profile(target).board_part
    wires = [
        AddWire(from_component=board, from_pin="21", to_component="ssd1306", to_pin="SDA"),
        AddWire(from_component=board, from_pin="GND", to_component="ssd1306", to_pin="GND", color=WireColor.BLACK),
    ]
    diagram = _render_diagram_json(board, "ssd1306", wires)
    assert diagram["parts"][0] == {"type": "board-esp32-devkit-c-v4", "id": board, "top": 0, "left": 0, "attrs": {}}
    assert diagram["connections"][1][:2] == [f"{board}:GND.1", "ssd1306:GND"]


@pytest.mark.parametrize("target", ["stm32f103"], indirect=True)
def test_build_failure_without_toolchain_skips_retry(target: str) -> None:
    state = DesignState(session_id="s", user_prompt="p", target_mcu=target, build_success=False)
    assert _route_after_build(state) == "simulate"
    assert state.code_retries == 0


def test_api_lists_mcus_and_rejects_unknown() -> None:
    client = TestClient(app)
    listed = {m["name"]: m for m in client.get("/api/mcus").json()}
    assert set(listed) == {"esp32", "rp2040", "stm32f103"}
    assert listed["rp2040"]["buildable"] is True
    assert listed["esp32"]["buildable"] is False
    assert client.get("/api/stream", params={"prompt": "x", "mcu": "atmega328p"}).status_code == 400
