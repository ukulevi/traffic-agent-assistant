"""Compatibility entrypoint for the split vision training test modules."""


def load_tests(loader, tests, pattern):
    if pattern is not None:
        return tests
    suite = loader.suiteClass()
    for name in (
        "tests.vision.test_vision_dataset_preparation",
        "tests.vision.test_vision_dataset_augmentation",
        "tests.vision.test_vision_relabel_and_promotion",
        "tests.vision.test_external_vision_models",
    ):
        suite.addTests(loader.loadTestsFromName(name))
    return suite
