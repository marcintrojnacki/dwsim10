"""Test dymny serwera DWSIM MCP: zdrowie, lista narzędzi, jeden bilans z wzorcem NIST.

Użycie: python3 enms/smoke.py http://127.0.0.1:5901 <token>
Wzorzec: 100 kg wody ciekłej 80 -> 40 °C przy 100 kPa, h 335,05 -> 167,62 kJ/kg (NIST), 4,6508 kWh.
"""
import json
import sys
import urllib.request

URL, TOKEN = sys.argv[1].rstrip("/"), sys.argv[2]
NAGLOWKI = {"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN}
_id = 0


def rpc(metoda, parametry=None):
    global _id
    _id += 1
    tresc = json.dumps({"jsonrpc": "2.0", "id": _id, "method": metoda, "params": parametry or {}}).encode()
    with urllib.request.urlopen(urllib.request.Request(URL + "/mcp", tresc, NAGLOWKI), timeout=120) as odp:
        dane = json.load(odp)
    if "error" in dane:
        raise RuntimeError(dane["error"])
    return dane["result"]


def narzedzie(nazwa, **argumenty):
    wynik = rpc("tools/call", {"name": nazwa, "arguments": argumenty})
    return json.loads("".join(c.get("text", "") for c in wynik.get("content", [])))


with urllib.request.urlopen(urllib.request.Request(URL + "/health", headers=NAGLOWKI), timeout=10) as odp:
    zdrowie = json.load(odp)
assert zdrowie == {"status": "ok", "auth": "enabled"}, zdrowie
try:
    urllib.request.urlopen(URL + "/health", timeout=10)
    raise AssertionError("serwer odpowiada bez tokenu")
except urllib.error.HTTPError as e:
    assert e.code == 401, e.code
rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}})
liczba = len(rpc("tools/list")["tools"])
assert liczba >= 50, liczba

fid = narzedzie("dwsim_flowsheet_create", name="smoke")["flowsheet_id"]
try:
    narzedzie("dwsim_thermo_add_compounds", flowsheet_id=fid, names=["Water"])
    narzedzie("dwsim_thermo_set_property_package", flowsheet_id=fid, name="Steam Tables (IAPWS-IF97)")
    narzedzie("dwsim_stream_add_material", flowsheet_id=fid, name="WLOT", temperature_K=353.15, pressure_Pa=1e5,
              composition={"Water": 1.0})
    narzedzie("dwsim_stream_set_conditions", flowsheet_id=fid, name="WLOT", mass_flow_kg_s=100.0)
    narzedzie("dwsim_stream_add_material", flowsheet_id=fid, name="WYLOT")
    narzedzie("dwsim_stream_add_energy", flowsheet_id=fid, name="Q")
    narzedzie("dwsim_unitop_add", flowsheet_id=fid, type="Cooler", name="U")
    narzedzie("dwsim_unitop_connect", flowsheet_id=fid, unitop="U", feed_stream="WLOT", product_stream="WYLOT",
              energy_product="Q")
    narzedzie("dwsim_unitop_set", flowsheet_id=fid, name="U",
              properties={"CalcMode": "OutletTemperature", "OutletTemperature": 313.15, "DeltaP": 0})
    assert narzedzie("dwsim_solve_run", flowsheet_id=fid, timeout_s=60)["ok"]
    q = narzedzie("dwsim_unitop_get_results", flowsheet_id=fid, name="Q")["properties"]
    kwh = abs(float(next(iter(q.values()))["value"])) / 3600
    assert abs(kwh / 4.650833 - 1) < 1e-3, kwh
    zapis = narzedzie("dwsim_flowsheet_save", flowsheet_id=fid, filepath="/data/smoke.dwxmz", compressed=True)
    assert "error" not in json.dumps(zapis).lower(), zapis
    # system plików tylko do odczytu: zapis poza /data i /tmp musi się nie udać
    poza = narzedzie("dwsim_flowsheet_save", flowsheet_id=fid, filepath="/opt/dwsim-mcp/smoke.dwxmz", compressed=True)
    assert "error" in poza, poza
finally:
    narzedzie("dwsim_flowsheet_close", flowsheet_id=fid)
print("smoke OK: %d narzędzi, B4 %.4f kWh (NIST 4,6508), zapis /data, odmowa zapisu poza /data" % (liczba, kwh))
