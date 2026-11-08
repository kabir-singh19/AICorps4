import numpy as np
import pytest

pd = pytest.importorskip("pandas")
from preprocessing import FeatureEncoder


def test_encoder_missing_unseen_categories_and_exact_reload():
    train = pd.DataFrame({"speed": [25.,45.,np.nan], "median": ["yes","no",None]})
    encoder = FeatureEncoder().fit(train)
    test = pd.DataFrame({"speed": [None,35.], "median": ["new",None]})
    encoded = encoder.transform(test)
    assert np.isfinite(encoded).all()
    assert encoder.medians["speed"] == 35
    np.testing.assert_array_equal(FeatureEncoder.from_dict(encoder.to_dict()).transform(test),encoded)


def test_all_missing_numeric_feature_cannot_be_imputed():
    with pytest.raises(ValueError):
        FeatureEncoder().fit(pd.DataFrame({"speed": [np.nan,np.nan]}))
