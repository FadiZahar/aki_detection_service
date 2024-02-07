admit_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240328132400||ADT^A01|||2.5",
                         "PID|1||444129||AYAT BURKE||19940216|F"]

discharge_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331035800||ADT^A03|||2.5",
                             "PID|1||829339"]

creatinine_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5",
                              "PID|1||125412",
                              "OBR|1||||||20240331003200",
                              "OBX|1|SN|CREATININE||127.5695463720204]"]

from prediction_system import preload_history, extract_type_and_mrn, extract_features

def test_preload_history():
    dataframe = preload_history()
    correct_column_names = ["age", "sex", "test_1", "test_2", "test_3", "test_4", "test_5"]
    actual_columns = [col[0] for col in dataframe.columns.tolist()]
    assert correct_column_names == actual_columns # check column names
    assert (dataframe["age"].nunique() == 0).all() # check all age values are None
    assert (dataframe["sex"].nunique() == 0).all() # check all sex values are None

def test_extract_type_and_mrn():
    assert extract_type_and_mrn(admit_message_example) == ("ADT^A01", "444129")
    assert extract_type_and_mrn(discharge_message_example) == ("ADT^A03", "829339")
    assert extract_type_and_mrn(creatinine_message_example) == ("ORU^R01", "125412")

def test_extract_features():
    pass

def main():
    test_preload_history()
    test_extract_type_and_mrn()
    
    
if __name__ == "__main__":
    main()
    print("All tests passed!")