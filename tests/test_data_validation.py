import json

from tools.data_validation import validate_records


def make_record(idx, exif, vector):
    return (idx, json.dumps(exif), json.dumps(vector))


def test_validate_records_filters_missing_and_short_vectors():
    slider_names = ["exposure", "contrast"]
    valid = make_record(
        1,
        {"iso": 100, "width": 4000, "height": 3000},
        [0.1, -0.2],
    )
    missing_exif = make_record(
        2,
        {"iso": 0, "width": 4000, "height": 3000},
        [0.5, 0.2],
    )
    short_vector = make_record(
        3,
        {"iso": 100, "width": 4000, "height": 3000},
        [0.4],
    )

    filtered, report = validate_records([valid, missing_exif, short_vector], slider_names)

    assert filtered == [valid]
    assert report.kept_records == 1
    assert report.dropped_missing_exif == 1
    assert report.dropped_short_vectors == 1


def test_validate_records_detects_outliers_with_iqr():
    slider_names = ["exposure"]
    normal_records = [
        make_record(i, {"iso": 100 + i, "width": 4000, "height": 3000}, [0.05])
        for i in range(20)
    ]
    extreme = make_record(
        999,
        {"iso": 100000, "width": 4000, "height": 3000},
        [10.0],
    )

    filtered, report = validate_records(
        normal_records + [extreme],
        slider_names,
        iqr_multiplier=1.5,
    )

    assert extreme not in filtered
    assert len(filtered) == len(normal_records)
    assert report.dropped_outliers == 1
