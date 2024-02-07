admit_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240328132400||ADT^A01|||2.5",
                         "PID|1||444129||AYAT BURKE||19940216|F"]

discharge_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331035800||ADT^A03|||2.5",
                             "PID|1||829339"]

creatinine_message_example = ["MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||20240331003200||ORU^R01|||2.5",
                              "PID|1||125412",
                              "OBR|1||||||20240331003200",
                              "OBX|1|SN|CREATININE||127.5695463720204]"]

from prediction_system import extract_type_and_mrn

def test_extract_type_and_mrn():
    assert extract_type_and_mrn(admit_message_example) == ("ADT^A01", "444129")
    assert extract_type_and_mrn(discharge_message_example) == ("ADT^A03", "829339")
    assert extract_type_and_mrn(creatinine_message_example) == ("ORU^R01", "125412")



def main():
    test_extract_type_and_mrn()
    
if __name__ == "__main__":
    main()
    print("All tests passed!")