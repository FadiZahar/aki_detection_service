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
        mrn = examine_message(creatinine_message_example, df_test, self.model)

        # Assert MRN is not returned for negative AKI prediction (like in this case)
        self.assertIsNone(mrn, "MRN should not be returned for negative AKI prediction")

        updated_tests = [127.57, 107.66, 116.58, 85.98, 100.95]
        self.assertEqual(updated_tests, list(df_test.loc["640400", ['test_1', 'test_2', 'test_3', 'test_4', 'test_5']]),
                         "Test results have not been updated and shifted properly")

    def test_examine_message_admit(self):
        admit_message_example = [
            "MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240328132400||ADT^A01|||2.5",
            "PID|1||755374||AYAT BURKE||19940216|F"
        ]
        df_test = self.df.copy()
        result = examine_message(admit_message_example, df_test, self.model)

        # Assert no MRN is returned for admit message
        self.assertIsNone(result, "No MRN should be returned for admit message")

        # Assert age and sex are updated correctly
        dob = "19940216"
        expected_age = calculate_age(dob)
        actual_age = df_test.loc["755374", "age"]
        self.assertEqual(actual_age, expected_age, "Age should be updated in the DataFrame")

        actual_sex = df_test.loc["755374", "sex"]
        self.assertEqual(actual_sex, 1, "Sex should be updated in the DataFrame")

    def test_examine_message_discharge(self):
        discharge_message_example = [
            "MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240601162800||ADT^A03|||2.5",
            "PID|1||521399"
        ]
        df_test = self.df.copy()
        # Process the discharge message
        mrn = examine_message(discharge_message_example, df_test, self.model)

        # Assert that no MRN is returned for a discharge message
        self.assertIsNone(mrn, "MRN should not be returned for a discharge message")

        # Assert that the new MRN is added with expected default or NaN values
        self.assertIn("521399", df_test.index, "New MRN should be added to the DataFrame for a discharge message")

        # Manually check each value in the row for the new MRN
        for col in df_test.columns:
            cell_value = df_test.at["521399", col]
            self.assertTrue(pd.isnull(cell_value), f"Value in column '{col}' for new MRN should be NaN or None")

    def test_new_patient_entry_creation(self):
        # Patient admission message for a new patient not in the DataFrame
        new_patient_admit_message = [
            "MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240328132400||ADT^A01|||2.5",
            "PID|1||999999||DOE JOHN||19880101|M"
        ]
        df_test = self.df.copy()
        _ = examine_message(new_patient_admit_message, df_test, self.model)
        self.assertIn("999999", df_test.index, "New patient MRN should be added to the DataFrame")
        self.assertTrue(pd.isnull(df_test.loc["999999", ["test_1", "test_2", "test_3", "test_4", "test_5"]]).all(),
                        "Test columns should be initialized with NaN for new patient")
        self.assertEqual(df_test.loc["999999", "age"], calculate_age("19880101"),
                         "Age should be correctly set for new patient")
        self.assertEqual(df_test.loc["999999", "sex"], 0, "Sex should be correctly set for new patient as male (0)")

    def test_update_new_patient_with_creatinine(self):
        # Assume the new patient now has a creatinine test result
        creatinine_message_new_patient = [
            "MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5",
            "PID|1||999999",
            "OBR|1||||||20240331003200",
            "OBX|1|SN|CREATININE||200"
        ]
        df_test = self.df.copy()
        _ = examine_message(creatinine_message_new_patient, df_test, self.model)
        for column in ["test_1", "test_2", "test_3", "test_4", "test_5"]:
            self.assertEqual(df_test.loc["999999", column], 200,
                             f"{column} should be populated with creatinine result 200 for new patient")

    def test_ignore_non_creatinine_result(self):
        # Non-creatinine test result message
        non_creatinine_message = [
            "MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5",
            "PID|1||555555",
            "OBR|1||||||20240331003200",
            "OBX|1|SN|GLUCOSE||100"
        ]
        df_test = self.df.copy()
        # Process the non-creatinine message
        _ = examine_message(non_creatinine_message, df_test, self.model)

        # Assert that the new MRN "999999" is added to the DataFrame
        self.assertIn("555555", df_test.index, "New MRN should be added to the DataFrame for a non-creatinine message")

        # Manually check each value in the row for the new MRN "999999"
        for col in df_test.columns:
            cell_value = df_test.at["555555", col]
            self.assertTrue(pd.isnull(cell_value),
                            f"Value in column '{col}' for new MRN '555555' should be NaN or None")

    def test_detect_aki_high_creatinine(self):
        # High creatinine level indicating AKI
        high_creatinine_message = [
            "MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5",
            "PID|1||640400",
            "OBR|1||||||20240331003200",
            "OBX|1|SN|CREATININE||300"  # Assuming this level of creatinine indicates AKI
        ]
        df_test = self.df.copy()
        mrn = examine_message(high_creatinine_message, df_test, self.model)
        self.assertIsNotNone(mrn, "MRN should be returned for positive AKI prediction due to high creatinine level")
        self.assertEqual(mrn, "640400", "MRN of the patient with high creatinine level should be returned")

    def test_to_mllp(self):
        ACK = [
            "MSH|^~\&|||||20240129093837||ACK|||2.5",
            "MSA|AA",
        ]
        ack = to_mllp(ACK)
        assert ack == b'\x0bMSH|^~\\&|||||20240129093837||ACK|||2.5\rMSA|AA\r\x1c\r'

    def test_from_mllp(self):
        test = b'\x0bMSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240102135300||ADT^A01|||2.5\rPID|1||497030||ROSCOE DOHERTY||19870515|M\r\x1c\r'
        expected = ['MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240102135300||ADT^A01|||2.5',
                    'PID|1||497030||ROSCOE DOHERTY||19870515|M']
        test = from_mllp(test)
        assert test == expected

        test = b'MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5\rPID|1||125412\rOBR|1||||||20240331003200\rOBX|1|SN|CREATININE||127.5695463720204'
        expected = ['SH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5', 'PID|1||125412',
                    'OBR|1||||||20240331003200', 'OBX|1|SN|CREATININE||127.5695463720']
        test = from_mllp(test)
        assert test == expected

        test = b'MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331035800||ADT^A03|||2.5\rPID|1||829339\r\x1c\r'
        expected = ['SH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240331035800||ADT^A03|||2.5', 'PID|1||829339']
        test = from_mllp(test)
        assert test == expected


class TestPreloadHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create or load the DataFrame (local database) once for all tests
        cls.dataframe = preload_history()  # Assuming this function returns a DataFrame

    def test_function_validity(self):
        # Test if the function executes without raising any exceptions
        try:
            preload_history()
        except Exception as e:
            self.fail(f"The function raised an exception: {e}")

    def test_is_dataframe(self):
        # Assert that the returned object is a DataFrame
        self.assertIsInstance(self.dataframe, pd.DataFrame, "Returned object is not a DataFrame")
    
    def test_column_names(self):
        correct_column_names = ["age", "sex", "test_1", "test_2", "test_3", "test_4", "test_5"]
        actual_columns = [col[0] for col in self.dataframe.columns.tolist()]
        # Assert correct column names
        self.assertEqual(correct_column_names, actual_columns, "Column names do not match")

    def test_all_age_values_none(self):
        # Assert all age values are None
        self.assertTrue((self.dataframe["age"].nunique() == 0).all(), "Not all age values are None")

    def test_all_sex_values_none(self):
        # Assert all sex values are None
        self.assertTrue((self.dataframe["sex"].nunique() == 0).all(), "Not all sex values are None")


if __name__ == '__main__':
    unittest.main()
