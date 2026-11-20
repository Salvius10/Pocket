"""The agent side of the A2UI contract. The Dart tests check the renderer side against the same file."""

import importlib.util
import json
from pathlib import Path

from pocket_common.a2ui import A2UI_VERSION, CATALOG_ID, COMPONENT_NAMES, ROOT_COMPONENT, build_messages
from pocket_common.layout import CATALOG, LayoutSpec

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "data" / "fixtures" / "a2ui_home.json"


def _generator():
    spec = importlib.util.spec_from_file_location("gen_a2ui_fixture", ROOT / "scripts" / "gen_a2ui_fixture.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_is_what_the_builder_emits_today() -> None:
    # If this fails, the builder changed: rerun scripts/gen_a2ui_fixture.py and make sure the
    # Dart contract test (apps/mobile/test/a2ui_contract_test.dart) still passes.
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == json.loads(json.dumps(_generator().contract()))


def test_every_message_carries_the_protocol_version() -> None:
    contract = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert contract["protocol_version"] == A2UI_VERSION == "1.0"
    assert all(m["version"] == A2UI_VERSION for m in contract["messages"])
    assert contract["messages"][0]["createSurface"]["catalogId"] == CATALOG_ID


def test_one_component_name_per_catalog_widget() -> None:
    assert set(COMPONENT_NAMES) == set(CATALOG)
    assert len(set(COMPONENT_NAMES.values())) == len(CATALOG)
    assert ROOT_COMPONENT not in COMPONENT_NAMES.values()


def test_messages_never_carry_money() -> None:
    spec = LayoutSpec.model_validate({"widgets": [{"type": "safe_to_spend"}, {"type": "pockets", "params": {"max_items": 3, "limit_paise": 5}},
                                                  {"type": "goals"}, {"type": "transactions"}]})
    text = json.dumps(build_messages(spec))
    assert "paise" not in text.lower() and "₹" not in text
