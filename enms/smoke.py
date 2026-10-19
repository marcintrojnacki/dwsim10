"""Test dymny serwera DWSIM MCP: zdrowie, lista narzędzi, jeden bilans z wzorcem NIST, reakcje.

Użycie: python3 enms/smoke.py http://127.0.0.1:5901 <token>
Wzorzec: 100 kg wody ciekłej 80 -> 40 °C przy 100 kPa, h 335,05 -> 167,62 kJ/kg (NIST), 4,6508 kWh.
Reakcje (narzędzia z Tools/Reactions, łatka EnMS): spalanie CH4/C2H6/CO/H2 przy λ = 1,6 w reaktorze konwersji
względem Automation3 (ten sam silnik, macOS), WGS w reaktorze równowagowym i w reaktorze Gibbsa.
"""
import json
import math
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


def odmowa(nazwa, **argumenty):
    """Komunikat błędu narzędzia, które musi odmówić."""
    wynik = rpc("tools/call", {"name": nazwa, "arguments": argumenty})
    assert wynik.get("isError"), (nazwa, argumenty, wynik)
    return json.loads(wynik["content"][0]["text"])["error"]


def ulamki(fid, strumien):
    faza = next(f for f in narzedzie("dwsim_stream_get_results", flowsheet_id=fid, name=strumien)["phases"]
                if f["name"] == "Mixture")
    return {c: v["mole_fraction"] for c, v in faza["compounds"].items()}


def moc_kw(fid, strumien):
    return float(next(iter(narzedzie("dwsim_unitop_get_results", flowsheet_id=fid, name=strumien)["properties"]
                           .values()))["value"])


# Masy molowe z bazy DWSIM [g/mol]. Skład w dwsim_stream_add_material bez przepływu całkowitego to przepływy masowe
# składników w kg/s (od #108 autora; z przepływem to ułamki masowe), więc mol/s zamieniamy na kg/s tymi samymi masami
# co silnik.
M = {"Methane": 16.04246, "Ethane": 30.06904, "Carbon monoxide": 28.0101, "Hydrogen": 2.01588, "Oxygen": 31.9988,
     "Nitrogen": 28.0134, "Carbon dioxide": 44.0095, "Water": 18.01528}
SPALANIE = {
    "CH4": ("Methane", {"Methane": -1, "Oxygen": -2, "Carbon dioxide": 1, "Water": 2}, 802.3),
    "C2H6": ("Ethane", {"Ethane": -1, "Oxygen": -3.5, "Carbon dioxide": 2, "Water": 3}, 1428.6),
    "CO": ("Carbon monoxide", {"Carbon monoxide": -1, "Oxygen": -0.5, "Carbon dioxide": 1}, 283.0),
    "H2": ("Hydrogen", {"Hydrogen": -1, "Oxygen": -0.5, "Water": 1}, 241.8),
}   # trzecia pozycja: LHV w 25 °C [kJ/mol], tablice NIST
# Wzorzec: Automation3 na macOS, ten sam przypadek (wylot 150 °C, Raoult), 17.10.2026.
Q_WZORZEC_KW = -597.5073506701666
X_WZORZEC = {"Methane": 0.0, "Ethane": 0.0, "Carbon monoxide": 0.0, "Hydrogen": 0.0, "Oxygen": 0.07346247884145196,
             "Nitrogen": 0.7369569305999624, "Carbon dioxide": 0.07109272145946961, "Water": 0.11848786909911602}
WGS = {"Carbon monoxide": -1, "Water": -1, "Carbon dioxide": 1, "Hydrogen": 1}
# K WGS w 700 K ze składu wylotu reaktora równowagowego w próbie szkicu narzędzi (17.10.2026, zasilanie
# x_CO 0,50002, wynik z pięcioma miejscami po przecinku); K nie zależy od zasilania. Pilnuje zmian silnika.
K_WGS_700, TOL_K = 9.3856, 1e-3


def k_wgs_nist(T):
    """Niezależny wzorzec: K = exp(-ΔG°/RT) z NIST WebBook (Chase 1998): równania Shomate'a w zakresach
    obejmujących 700 K (CO 298–1300 K, H2O 500–1700 K, CO2 298–1200 K, H2 298–1000 K) i ΔfH° 298,15 K
    (CO -110,53, H2O -241,826, CO2 -393,52 kJ/mol). Gaz doskonały, Δn = 0, więc K nie zależy od ciśnienia."""
    shomate = {"Carbon monoxide": (25.56759, 6.096130, 4.054656, -2.671301, 0.131021, -118.0089, 227.3665, -110.5271, -110.53),
               "Water": (30.09200, 6.832514, 6.793435, -2.534480, 0.082139, -250.8810, 223.3967, -241.8264, -241.826),
               "Carbon dioxide": (24.99735, 55.18696, -33.69137, 7.948387, -0.136638, -403.6075, 228.2431, -393.5224, -393.52),
               "Hydrogen": (33.066178, -11.363417, 11.432816, -2.772874, -0.158558, -9.980797, 172.707974, 0.0, 0.0)}
    t, dh, ds = T / 1000, 0.0, 0.0
    for c, n in WGS.items():
        A, B, C, D, E, F, G, H, hf = shomate[c]
        dh += n * (hf + A * t + B * t**2 / 2 + C * t**3 / 3 + D * t**4 / 4 - E / t + F - H)       # kJ/mol
        ds += n * (A * math.log(t) + B * t + C * t**2 / 2 + D * t**3 / 3 - E / (2 * t**2) + G)  # J/(mol·K)
    return math.exp(-(dh * 1000 - T * ds) / (8.314462618 * T))


# 17.10.2026: NIST 9,4358, DWSIM (PR, 1 atm) 9,3856, różnica -0,53%; ±1% obejmuje rozrzut źródeł danych.
K_WGS_700_NIST, TOL_K_NIST = k_wgs_nist(700.0), 1e-2


def spalanie():
    """Reaktor konwersji: paliwo mieszane przy λ = 1,6, konwersja 100%, wylot 150 °C."""
    paliwo = {"Methane": 0.6, "Ethane": 0.05, "Carbon monoxide": 0.2, "Hydrogen": 0.15}   # mol/s
    o2 = 1.6 * sum(-st["Oxygen"] * paliwo[baza] for baza, st, _ in SPALANIE.values())
    n = dict(paliwo, Oxygen=o2, Nitrogen=o2 * 79 / 21)
    fid = narzedzie("dwsim_flowsheet_create", name="smoke-spalanie")["flowsheet_id"]
    try:
        narzedzie("dwsim_thermo_add_compounds", flowsheet_id=fid, names=list(M))
        narzedzie("dwsim_thermo_set_property_package", flowsheet_id=fid, name="Raoult's Law")
        narzedzie("dwsim_stream_add_material", flowsheet_id=fid, name="SUB", temperature_K=298.15, pressure_Pa=101325.0,
                  composition={c: n.get(c, 0.0) * M[c] / 1000 for c in M})
        narzedzie("dwsim_stream_set_conditions", flowsheet_id=fid, name="SUB", molar_flow_mol_s=sum(n.values()))
        for s in ("PROD", "CIECZ"):
            narzedzie("dwsim_stream_add_material", flowsheet_id=fid, name=s)
        narzedzie("dwsim_stream_add_energy", flowsheet_id=fid, name="Q")
        # kontrole przed utworzeniem reakcji
        assert "Propane" in odmowa("dwsim_reaction_add_conversion", flowsheet_id=fid, name="X",
                                   stoichiometry={"Propane": -1, "Oxygen": -5}, base_compound="Propane")
        assert "O +1" in odmowa("dwsim_reaction_add_conversion", flowsheet_id=fid, name="X",
                                stoichiometry={"Methane": -1, "Oxygen": -1.5, "Carbon dioxide": 1, "Water": 2},
                                base_compound="Methane")
        assert "reactant" in odmowa("dwsim_reaction_add_conversion", flowsheet_id=fid, name="X",
                                    stoichiometry=SPALANIE["H2"][1], base_compound="Water")
        assert "phase" in odmowa("dwsim_reaction_add_conversion", flowsheet_id=fid, name="X",
                                 stoichiometry=SPALANIE["H2"][1], base_compound="Hydrogen", phase="Gas")
        narzedzie("dwsim_reactionset_create", flowsheet_id=fid, name="Spalanie")
        for nazwa, (baza, st, lhv) in SPALANIE.items():
            r = narzedzie("dwsim_reaction_add_conversion", flowsheet_id=fid, name=nazwa, stoichiometry=st,
                          base_compound=baza, conversion="100", phase="Vapor", reaction_set="Spalanie")
            assert abs(-r["heat_of_reaction_kJ_kmol"] / 1000 / lhv - 1) < 1e-3, (nazwa, r)
        assert "already exists" in odmowa("dwsim_reaction_add_conversion", flowsheet_id=fid, name="H2",
                                          stoichiometry=SPALANIE["H2"][1], base_compound="Hydrogen")
        zestawy = {z["id"]: z for z in narzedzie("dwsim_reaction_list", flowsheet_id=fid)["reaction_sets"]}
        assert [r["reaction"] for r in zestawy["Spalanie"]["reactions"]] == list(SPALANIE), zestawy
        narzedzie("dwsim_unitop_add", flowsheet_id=fid, type="ConversionReactor", name="R")
        narzedzie("dwsim_unitop_connect", flowsheet_id=fid, unitop="R", feed_stream="SUB", product_stream="PROD")
        narzedzie("dwsim_unitop_connect", flowsheet_id=fid, unitop="R", product_stream="CIECZ", product_port=1,
                  energy_feed="Q", energy_feed_port=1)
        narzedzie("dwsim_unitop_set", flowsheet_id=fid, name="R", properties={
            "ReactionSetID": "Spalanie", "ReactorOperationMode": "OutletTemperature", "OutletTemperature": 423.15})
        wynik = narzedzie("dwsim_solve_run", flowsheet_id=fid, timeout_s=60)
        assert wynik["ok"], wynik
        x = ulamki(fid, "PROD")
        dx = max(abs(x[c] - X_WZORZEC[c]) for c in X_WZORZEC)
        q = moc_kw(fid, "Q")
        assert dx < 1e-9, x
        assert abs(q / Q_WZORZEC_KW - 1) < 1e-6, q
        return q, dx
    finally:
        narzedzie("dwsim_flowsheet_close", flowsheet_id=fid)


def wgs(typ):
    """CO + H2O = CO2 + H2 przy 700 K i 1 atm, zasilanie CO/H2O 0,5/0,5 mol/s; skład wylotu."""
    fid = narzedzie("dwsim_flowsheet_create", name="smoke-wgs")["flowsheet_id"]
    try:
        narzedzie("dwsim_thermo_add_compounds", flowsheet_id=fid, names=list(WGS))
        narzedzie("dwsim_thermo_set_property_package", flowsheet_id=fid, name="Peng-Robinson (PR)")
        narzedzie("dwsim_stream_add_material", flowsheet_id=fid, name="F", temperature_K=700.0, pressure_Pa=101325.0,
                  composition={c: (0.5 * M[c] / 1000 if c in ("Carbon monoxide", "Water") else 0.0) for c in WGS})
        for s in ("P", "L"):
            narzedzie("dwsim_stream_add_material", flowsheet_id=fid, name=s)
        narzedzie("dwsim_stream_add_energy", flowsheet_id=fid, name="Q")
        narzedzie("dwsim_unitop_add", flowsheet_id=fid, type=typ, name="R")
        narzedzie("dwsim_unitop_connect", flowsheet_id=fid, unitop="R", feed_stream="F", product_stream="P")
        narzedzie("dwsim_unitop_connect", flowsheet_id=fid, unitop="R", product_stream="L", product_port=1,
                  energy_feed="Q", energy_feed_port=1)
        narzedzie("dwsim_unitop_set", flowsheet_id=fid, name="R", properties={"ReactorOperationMode": "Isothermic"})
        if typ == "EquilibriumReactor":
            r = narzedzie("dwsim_reaction_add_equilibrium", flowsheet_id=fid, name="WGS", stoichiometry=WGS,
                          base_compound="Carbon monoxide")
            assert r["keq_from"] == "Gibbs" and r["reaction_set"] == "DefaultSet", r
        else:
            wynik = narzedzie("dwsim_solve_run", flowsheet_id=fid, timeout_s=60)
            assert not wynik["ok"] and "Element Matrix is not defined" in json.dumps(wynik), wynik
            r = narzedzie("dwsim_reactor_set_compounds", flowsheet_id=fid, name="R", compounds=list(WGS))
            assert sorted(r["elements"]) == ["C", "H", "O"], r
        wynik = narzedzie("dwsim_solve_run", flowsheet_id=fid, timeout_s=60)
        assert wynik["ok"], wynik
        return ulamki(fid, "P")
    finally:
        narzedzie("dwsim_flowsheet_close", flowsheet_id=fid)


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
# opcjonalnie: pobranie zapisanego schematu przez kontener dwsim-mcp-pliki (trzeci argument: adres katalogu pliki/)
if len(sys.argv) > 3:
    with urllib.request.urlopen(urllib.request.Request(sys.argv[3].rstrip("/") + "/smoke.dwxmz", headers=NAGLOWKI),
                                timeout=30) as odp:
        assert odp.read(2) == b"PK", "pobrany plik nie jest archiwum dwxmz"
    try:
        urllib.request.urlopen(sys.argv[3].rstrip("/") + "/smoke.dwxmz", timeout=10)
        raise AssertionError("pliki dostępne bez tokenu")
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403), e.code
    print("pobieranie pliku schematu: OK")
q_spal, dx_spal = spalanie()
x_rown, x_gibbs = wgs("EquilibriumReactor"), wgs("GibbsReactor")
k_rown = x_rown["Carbon dioxide"] * x_rown["Hydrogen"] / (x_rown["Carbon monoxide"] * x_rown["Water"])
assert abs(k_rown / K_WGS_700 - 1) < TOL_K, (k_rown, x_rown)
assert abs(k_rown / K_WGS_700_NIST - 1) < TOL_K_NIST, (k_rown, K_WGS_700_NIST)
dx_wgs = max(abs(x_rown[c] - x_gibbs[c]) for c in WGS)
assert dx_wgs < 1e-3, (x_rown, x_gibbs)
print("smoke OK: %d narzędzi, B4 %.4f kWh (NIST 4,6508), zapis /data, odmowa zapisu poza /data" % (liczba, kwh))
print("reakcje OK: spalanie λ = 1,6 Q = %.6f kW (Automation3 %.6f), max |Δx| %.1e; WGS 700 K K = %.4f "
      "(NIST %.4f), x_CO %.6f, Gibbs - równowagowy max |Δx| %.1e" % (q_spal, Q_WZORZEC_KW, dx_spal, k_rown, K_WGS_700_NIST,
                                                       x_rown["Carbon monoxide"], dx_wgs))
