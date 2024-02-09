from prediction_system import preload_history
import pandas as pd


admit_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240328132400||ADT^A01|||2.5",
                         "PID|1||444129||AYAT BURKE||19940216|F"]

discharge_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331035800||ADT^A03|||2.5",
                             "PID|1||829339"]

creatinine_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5",
                              "PID|1||125412",
                              "OBR|1||||||20240331003200",
                              "OBX|1|SN|CREATININE||127.5695463720204]"]


# Data for creating the DataFrame
data = {
    "MRN": ["640400", "755374", "442925", "160064", "976"],
    "age": [33, 50, 16, 42, 24],
    "sex": [0, 1, 1, 0, 0],
    "test_1": [107.66, 112.34, 73.93, 84.54, 104.02],
    "test_2": [116.58, 94.65, 98.37, 88.10, 82.11],
    "test_3": [85.98, 89.37, 82.16, 76.24, 107.74],
    "test_4": [100.95, 98.63, 78.02, 79.46, 107.71],
    "test_5": [73.49, 80.49, 96.94, 86.66, 74.54]
}

# Creating the DataFrame
df = pd.DataFrame(data)

# Setting 'MRN' as the index of the DataFrame
df.set_index("MRN", inplace=True)


def test_preload_history():
    dataframe = preload_history()
    print(dataframe.head(10))
    correct_column_names = ["age", "sex", "test_1", "test_2", "test_3", "test_4", "test_5"]
    actual_columns = [col[0] for col in dataframe.columns.tolist()]
    assert correct_column_names == actual_columns # check column names
    assert (dataframe["age"].nunique() == 0).all() # check all age values are None
    assert (dataframe["sex"].nunique() == 0).all() # check all sex values are None

def test_extract_features():
    pass

def main():
    test_preload_history()
    
if __name__ == "__main__":
    main()
    print("All tests passed!")