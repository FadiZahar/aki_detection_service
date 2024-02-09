import unittest
from prediction_system import *

class preload_history_tests(unittest.TestCase):

    def test_function_validity(self):
        # Test if the function executes without raising any exceptions
        try:
            preload_history()
        except Exception as e:
            self.fail(f"The function raised an exception: {e}")
            
    @classmethod
    def setUpClass(cls):
        # Create or load the DataFrame (local database) once for all tests
        cls.dataframe = preload_history()  # Assuming this function returns a DataFrame

    def test_is_dataframe(self):
        # Assert that the returned object is a DataFrame
        self.assertIsInstance(self.dataframe, pd.DataFrame, "Returned object is not a DataFrame")
    
    def test_column_names(self):
        correct_column_names = ["age", "sex", "test_1", "test_2", "test_3", "test_4", "test_5"]
        actual_columns = self.dataframe.columns.tolist()
        # Assert correct column names
        self.assertEqual(correct_column_names, actual_columns, "Column names do not match")

    def test_all_age_values_none(self):
        # Assert all age values are None
        self.assertTrue((self.dataframe["age"].nunique() == 0).all(), "Not all age values are None")

    def test_all_sex_values_none(self):
        # Assert all sex values are None
        self.assertTrue((self.dataframe["sex"].nunique() == 0).all(), "Not all sex values are None")

