import pytest

from kinetic_captions.model_manager import ModelInstallError, resolve_model_name


def test_resolve_model_name_aliases() -> None:
    assert resolve_model_name("small") == "small"
    assert resolve_model_name("medium") == "medium"
    assert resolve_model_name("large") == "large-v3"


def test_resolve_model_name_rejects_unknown() -> None:
    with pytest.raises(ModelInstallError):
        resolve_model_name("tiny")
