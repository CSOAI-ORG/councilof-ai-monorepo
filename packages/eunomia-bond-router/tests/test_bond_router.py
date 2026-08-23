import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from eunomia_bond_router import cobol_parser as c
def test_parse():
    l = c.parse_copybook("01 R.\n 05 ID PIC X(10).\n 05 NAME PIC X(20).\n 05 AMT PIC 9(8)V99.")
    assert [f.name for f in l["fields"]] == ["ID","NAME","AMT"]
    assert l["length"] == 10+20+10
def test_record():
    l = c.parse_copybook("01 R.\n 05 ID PIC X(10).\n 05 AMT PIC 9(8)V99.")
    r = c.parse_record("1234567890"+"0000001234", l)
    assert r["id"] == "1234567890"
if __name__ == "__main__":
    test_parse(); test_record(); print("PASS")
