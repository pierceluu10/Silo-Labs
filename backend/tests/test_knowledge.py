from __future__ import annotations

import pytest

from app.knowledge.graph import (
    PinAssignment,
    PinConflictError,
    RPGraph,
    UnknownPeripheralError,
    UnknownRegisterError,
    get_graph,
)


@pytest.fixture(scope="module")
def graph() -> RPGraph:
    return get_graph()


def test_loads_all_rp2040_peripherals(graph: RPGraph) -> None:
    names = graph.list_peripherals()
    for expected in ("I2C0", "I2C1", "SPI0", "SPI1", "UART0", "UART1", "PWM", "ADC"):
        assert expected in names, f"SVD missing {expected}"


def test_i2c0_pin_options_include_canonical_set(graph: RPGraph) -> None:
    pins = graph.get_peripheral_pins("I2C", 0)
    assert "SDA" in pins and "SCL" in pins
    assert {4, 8, 12, 16, 20}.issubset(set(pins["SDA"]))
    assert {5, 9, 13, 17, 21}.issubset(set(pins["SCL"]))
    assert 0 not in pins["SDA"], "GP0 must be excluded (reserved for UART0 debug)"
    assert 1 not in pins["SCL"], "GP1 must be excluded (reserved for UART0 debug)"


def test_i2c1_pins_disjoint_from_i2c0(graph: RPGraph) -> None:
    i2c0 = graph.get_peripheral_pins("I2C", 0)
    i2c1 = graph.get_peripheral_pins("I2C", 1)
    assert set(i2c0["SDA"]).isdisjoint(i2c1["SDA"])
    assert set(i2c0["SCL"]).isdisjoint(i2c1["SCL"])


def test_i2c0_ic_con_authoritative_address(graph: RPGraph) -> None:
    reg = graph.get_register("I2C0", "IC_CON")
    assert reg["address"] == 0x40044000
    assert reg["size_bits"] == 32
    assert "SPEED" in reg["fields"]
    speed = reg["fields"]["SPEED"]
    assert speed["offset"] == 1
    assert speed["width"] == 2


def test_unknown_register_raises(graph: RPGraph) -> None:
    with pytest.raises(UnknownRegisterError):
        graph.get_register("I2C0", "NOT_A_REAL_REGISTER")
    with pytest.raises(UnknownPeripheralError):
        graph.get_register("I2C9", "IC_CON")


def test_clock_sources_for_clk_sys(graph: RPGraph) -> None:
    sources = graph.get_clock_sources("CLK_SYS")
    assert set(sources) >= {"PLL_SYS", "XOSC", "ROSC"}


def test_check_pin_conflicts_raises_on_double_assign(graph: RPGraph) -> None:
    with pytest.raises(PinConflictError):
        graph.check_pin_conflicts(
            [PinAssignment(pin_number=4, function="I2C0_SDA"),
             PinAssignment(pin_number=4, function="UART1_TX")]
        )


def test_check_pin_conflicts_allows_unique(graph: RPGraph) -> None:
    graph.check_pin_conflicts(
        [PinAssignment(pin_number=4, function="I2C0_SDA"),
         PinAssignment(pin_number=5, function="I2C0_SCL")]
    )


def test_errata_lookup_by_trigger(graph: RPGraph) -> None:
    matches = graph.get_errata_by_trigger(["I2C"])
    assert any(e["id"] == "E4" for e in matches)


def test_wokwi_component_lookup(graph: RPGraph) -> None:
    comp = graph.get_wokwi_component("bme280")
    assert comp is not None
    # Wokwi has no native BME280 part; we use board-bmp180 (T+P sensor) as
    # the closest stand-in so the diagram passes wokwi-cli validation.
    assert comp["type"] == "board-bmp180"
    assert "SDA" in comp["pins"]


def test_svd_summary_non_empty(graph: RPGraph) -> None:
    summary = graph.svd_summary()
    assert "I2C0" in summary
    assert "0x40044000" in summary
