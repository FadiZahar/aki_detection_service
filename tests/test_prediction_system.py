import unittest
from prediction_system import *

class TestBoard(unittest.TestCase):
    def setUp(self):
        pass

    def test_preload_history(self):
            dataframe = preload_history()
            print(dataframe.head(10))
            correct_column_names = ["age", "sex", "test_1", "test_2", "test_3", "test_4", "test_5"]
            actual_columns = [col[0] for col in dataframe.columns.tolist()]
            assert correct_column_names == actual_columns # check column names
            assert (dataframe["age"].nunique() == 0).all() # check all age values are None
            assert (dataframe["sex"].nunique() == 0).all() # check all sex values are None


    def test_preload_history(self):
        dataframe = preload_history()
        print(dataframe.head(10))
        correct_column_names = ["age", "sex", "test_1", "test_2", "test_3", "test_4", "test_5"]
        actual_columns = [col[0] for col in dataframe.columns.tolist()]
        assert correct_column_names == actual_columns # check column names
        assert (dataframe["age"].nunique() == 0).all() # check all age values are None
        assert (dataframe["sex"].nunique() == 0).all() # check all sex values are None
