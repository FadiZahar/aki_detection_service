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

    def test_to_mllp(self):
        ACK = [
            "MSH|^~\&|||||20240129093837||ACK|||2.5",
            "MSA|AA",
        ]
        ack = to_mllp(ACK)
        assert ack == b'\x0bMSH|^~\\&|||||20240129093837||ACK|||2.5\rMSA|AA\r\x1c\r'

    def test_from_mllp(self):
        test = b'\x0bMSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240102135300||ADT^A01|||2.5\rPID|1||497030||ROSCOE DOHERTY||19870515|M\r\x1c\r'
        expected = ['MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240102135300||ADT^A01|||2.5', 'PID|1||497030||ROSCOE DOHERTY||19870515|M']
        test = from_mllp(test)
        assert test == expected

        test = b'MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5\rPID|1||125412\rOBR|1||||||20240331003200\rOBX|1|SN|CREATININE||127.5695463720204'
        expected = ['SH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5', 'PID|1||125412', 'OBR|1||||||20240331003200', 'OBX|1|SN|CREATININE||127.5695463720']
        test = from_mllp(test)
        assert test == expected

        test = b'MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331035800||ADT^A03|||2.5\rPID|1||829339\r\x1c\r'
        expected = ['SH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240331035800||ADT^A03|||2.5', 'PID|1||829339']
        test = from_mllp(test)
        assert test == expected
