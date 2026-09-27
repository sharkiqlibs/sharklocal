"""Tests for sharklocal.compat: the app's per-model feature rules."""

import pytest

from sharklocal.compat import MODEL_FAMILIES, RV3000_MODELS, RobotProfile


def test_the_app_table_is_carried_whole():
    assert len(MODEL_FAMILIES) > 600
    assert MODEL_FAMILIES["RV1000A"] == "Mesa1"


def test_rv3000_gets_its_settings_rows_and_mask_features():
    p = RobotProfile("RV3000-001D5F7F")
    assert p.classification == "Three60"
    assert p.is_rv3000 and p.has_underglow_lights and p.has_button_sounds
    # 0x...7F: WetDry, FanJet, AED, Series 3, Bluetooth, Lidar, Floor Detect.
    assert p.has_auto_empty is True
    assert p.has_fan_jet is True
    assert not p.has_carpet_boost
    assert RV3000_MODELS >= {"RV3000-001D5F7F"}


def test_opp_gets_carpet_controls_but_not_matrix():
    p = RobotProfile("RV2500HOP")
    assert p.is_opp and p.has_carpet_boost and p.has_carpet_detect
    assert p.has_ultra_clean is False
    assert p.has_auto_empty is True
    assert not p.has_underglow_lights


def test_random_bounce_gets_almost_nothing():
    p = RobotProfile("RV750")
    assert p.classification == "RandomBounce"
    assert (p.has_map, p.has_volume, p.do_not_disturb, p.has_pin_drop) == (False, False, False, False)


def test_spot_lidar_has_no_pin_drop():
    p = RobotProfile("RV2100AB")
    assert p.has_map is True
    assert p.has_pin_drop is False
    assert p.has_ultra_clean is False


def test_prefix_letters():
    # A (not VA) = self-emptying dock; X = FanJet.
    three60 = next(m for m, f in MODEL_FAMILIES.items() if f == "Three60" and "A" in m.split("-")[0] and "VA" not in m)
    assert RobotProfile(three60).has_auto_empty is True
    valley = next((m for m, f in MODEL_FAMILIES.items() if f.startswith("Valley") and "A" in m.split("-")[0] and "VA" not in m), None)
    if valley:
        assert RobotProfile(valley).has_auto_empty is False
    assert RobotProfile("RV2500VA").has_auto_empty is False
    assert RobotProfile("RV2000DX").has_fan_jet is True


def test_a_model_missing_from_the_table_is_unknown_not_false():
    # A retail SKU is not the cloud model string: family answers are unknown,
    # exact product lines are simply not matched.
    p = RobotProfile("RV2610BFCA")
    assert not p.known
    assert p.family is None and p.classification is None
    assert (p.has_map, p.has_explore, p.do_not_disturb, p.has_volume, p.has_pin_drop, p.has_mopping) == (None,) * 6
    assert (p.has_underglow_lights, p.has_carpet_boost, p.is_360ez) == (False, False, False)


def test_a_malformed_mask_is_ignored():
    assert RobotProfile("RV3000-ZZZZZZZZ")._mask("AED") is None


from sharklocal.compat import ROBOT_TYPES, Capabilities, capabilities_for_model, robot_type


@pytest.mark.parametrize(
    "model, kind",
    [
        ("RV3000-001D5F7F", "rv3000"),
        ("RV2500HOP", "lidar_carpet"),
        ("RV2100AB", "spot_lidar"),
        ("RV1000A", "map"),
        ("RV750", "basic"),
        ("RV1100AA", "air"),
        ("RV2000DX", "lidar"),
        ("RV2610BFCA", None),
    ],
)
def test_every_model_falls_into_one_robot_type(model, kind):
    assert robot_type(RobotProfile(model)) == kind


def test_every_table_model_has_a_type():
    assert {robot_type(RobotProfile(m)) for m in MODEL_FAMILIES} <= set(ROBOT_TYPES)


@pytest.mark.parametrize("model", sorted(MODEL_FAMILIES))
def test_a_robot_type_answers_like_its_models(model):
    # The simple configuration must agree with the app's per-model rules on
    # every feature the app decides for that model.
    profile = RobotProfile(model)
    caps = capabilities_for_model(model)
    for feature in (
        "has_map", "has_explore", "has_pin_drop", "has_ultra_clean", "has_recharge_resume",
        "has_auto_empty", "has_fan_jet", "do_not_disturb", "has_volume",
        "has_underglow_lights", "has_button_sounds", "has_carpet_boost", "has_carpet_detect",
    ):
        assert getattr(caps, feature) == bool(getattr(profile, feature)), (model, feature)


def test_unknown_model_has_no_capabilities():
    assert capabilities_for_model("RV2610BFCA") is None


def test_extras_are_asked_not_derived():
    caps = Capabilities("lidar", self_empty_dock=True, clean_edge=False)
    assert caps.has_auto_empty and not caps.has_fan_jet
    assert caps.has_pin_drop and caps.has_ultra_clean and caps.do_not_disturb and caps.has_volume
    assert not (caps.has_underglow_lights or caps.has_carpet_boost)
