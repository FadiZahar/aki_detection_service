import unittest
import pandas as pd
import pickle
from prediction_system import *


class TestExamineMessageModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load the actual model from a pickle file
        with open("trained_model.pkl", "rb") as file:
            cls.model = pickle.load(file)

        # Set up DataFrame for testing
        df_test = {
            "MRN": ["640400", "755374", "442925", "160064", "164125"],
            "age": [33, 50, 16, 42, 24],
            "sex": [0, 1, 1, 0, 0],
            "test_1": [107.66, 112.34, 73.93, 84.54, 104.02],
            "test_2": [116.58, 94.65, 98.37, 88.10, 82.11],
            "test_3": [85.98, 89.37, 82.16, 76.24, 107.74],
            "test_4": [100.95, 98.63, 78.02, 79.46, 107.71],
            "test_5": [104.96, 97.07, 70.88, 83.36, 90.60]
        }
        cls.df = pd.DataFrame(df_test)
        cls.df.set_index("MRN", inplace=True)

    def test_examine_message_creates(self):
        creatinine_message_example = [
            "MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5",
            "PID|1||640400",
            "OBR|1||||||20240331003200",
            "OBX|1|SN|CREATININE||127.57"
        ]
        df_test = self.df.copy()
        # mrn = examine_message(creatinine_message_example, df_test, self.model)

        # Assert MRN is not returned for negative AKI prediction (like in this case)
        # self.assertIsNone(mrn, "MRN should not be returned for negative AKI prediction")

        updated_tests = [127.57, 107.66, 116.58, 85.98, 100.95]
        # self.assertEqual(updated_tests, list(df_test.loc["640400", ['test_1', 'test_2', 'test_3', 'test_4', 'test_5']]),



if __name__ == '__main__':
    unittest.main()
