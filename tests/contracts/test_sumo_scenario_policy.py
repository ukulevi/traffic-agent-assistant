import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "generate_sumo_scenarios", ROOT / "scripts" / "data_prep" / "generate_sumo_scenarios.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SumoScenarioPolicyTest(unittest.TestCase):
    def test_family_split_has_event_coverage_without_leakage(self) -> None:
        family_splits = {}
        event_splits = {event: set() for event in MODULE.EVENT_TYPES}
        counts = {"train": 0, "val": 0, "test": 0}
        for event_index, event in enumerate(MODULE.EVENT_TYPES):
            for node in range(20):
                family = f"{event}:{node}"
                split = MODULE.split_for_family(node, event_index)
                family_splits.setdefault(family, split)
                self.assertEqual(family_splits[family], split)
                event_splits[event].add(split)
                counts[split] += 2
        self.assertTrue(all(splits == {"train", "val", "test"}
                            for splits in event_splits.values()))
        self.assertEqual(counts, {"train": 140, "val": 30, "test": 30})

    def test_incident_parameters_stay_in_contract_range(self) -> None:
        for event in MODULE.EVENT_TYPES:
            parameters = MODULE.scenario_parameters(event, 3, 1)
            self.assertGreaterEqual(parameters["lane_closure_ratio"], 0)
            self.assertLessEqual(parameters["lane_closure_ratio"], 1)
            self.assertGreater(parameters["demand_multiplier"], 0)
            self.assertIn(parameters["duration_minutes"], {10, 15, 20, 30})


if __name__ == "__main__":
    unittest.main()
