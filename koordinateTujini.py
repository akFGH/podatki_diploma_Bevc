from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests


# ============================================================
# 1. NASTAVITVE
# ============================================================

GEONAMES_USERNAME = "anita123"

MAPA = Path(__file__).resolve().parent

VHODNA_DATOTEKA = MAPA / "Jutro24.csv"

MAPA_REZULTATOV = MAPA / "rezultati"
MAPA_REZULTATOV.mkdir(exist_ok=True)

PREDPOMNILNIK = MAPA / "geonames_cache.json"

DOMACI_KRAJI_CSV = MAPA_REZULTATOV / "domaci_in_jugoslovanski_kraji.csv"
TUJI_KRAJI_CSV = MAPA_REZULTATOV / "tuji_kraji_s_koordinatami.csv"
POSEBNA_OBMOCJA_CSV = MAPA_REZULTATOV / "zgodovinska_in_regionalna_obmocja.csv"
SLOVENSKA_NARODNA_OBMOCJA_CSV = MAPA_REZULTATOV / "slovenska_narodna_obmocja_zunaj_jugoslavije.csv"
ROCNI_PREGLED_CSV = MAPA_REZULTATOV / "za_rocni_pregled.csv"
VSI_REZULTATI_CSV = MAPA_REZULTATOV / "vsi_obdelani_zapisi.csv"
KANDIDATI_CSV = MAPA_REZULTATOV / "geonames_kandidati.csv"

GEONAMES_URL = "https://secure.geonames.org/searchJSON"

# Zamik med novimi zahtevami. Rezultati iz predpomnilnika ne čakajo.
ZAMIK_MED_ZAHTEVAMI = 1.1

# Koliko kandidatov zahtevamo od GeoNames.
STEVILO_KANDIDATOV = 10


# ============================================================
# 2. DRŽAVE PROSTORA NEKDANJE JUGOSLAVIJE
# ============================================================

JUGOSLOVANSKE_KODE = {
    "SI",  # Slovenija
    "HR",  # Hrvaška
    "BA",  # Bosna in Hercegovina
    "RS",  # Srbija
    "ME",  # Črna gora
    "MK",  # Severna Makedonija
    "XK",  # Kosovo
}


# ============================================================
# 2A. SLOVENSKA NARODNA OBMOČJA ZUNAJ KRALJEVINE JUGOSLAVIJE
#
# Razmejitev je raziskovalna in približna. Temelji na današnji
# državni pripadnosti, koordinatah in upravnih imenih GeoNames.
# Uporablja se samo za naseljene kraje (feature class P), zato
# države Italija, Avstrija in Madžarska niso napačno uvrščene.
# Mejni primeri dobijo oznako, da jih je treba ročno preveriti.
# ============================================================

# Ročno določeni kraji imajo prednost pred koordinatnimi pravili.
# Ključi naj bodo standardizirana ali GeoNamesova imena v mali pisavi.
SLOVENSKA_NARODNA_OBMOCJA_ROCNO = {
    # Italija – Tržaško, Goriško, Beneška Slovenija, Rezija, Kanalska dolina
    "trieste": ("Primorska pod Italijo", "Tržaško"),
    "trst": ("Primorska pod Italijo", "Tržaško"),
    "gorizia": ("Primorska pod Italijo", "Goriško"),
    "gorica": ("Primorska pod Italijo", "Goriško"),
    "monfalcone": ("Primorska pod Italijo", "Goriško"),
    "tržič": ("Primorska pod Italijo", "Goriško"),
    "cividale del friuli": ("Primorska pod Italijo", "Beneška Slovenija"),
    "čedad": ("Primorska pod Italijo", "Beneška Slovenija"),
    "san pietro al natisone": ("Primorska pod Italijo", "Beneška Slovenija"),
    "špeter slovenov": ("Primorska pod Italijo", "Beneška Slovenija"),
    "resia": ("Primorska pod Italijo", "Rezija"),
    "rezija": ("Primorska pod Italijo", "Rezija"),
    "tarvisio": ("Primorska pod Italijo", "Kanalska dolina"),
    "trbiž": ("Primorska pod Italijo", "Kanalska dolina"),

    # Avstrija – južna Koroška
    "klagenfurt am wörthersee": ("Koroška pod Avstrijo", "Celovško polje"),
    "klagenfurt": ("Koroška pod Avstrijo", "Celovško polje"),
    "celovec": ("Koroška pod Avstrijo", "Celovško polje"),
    "villach": ("Koroška pod Avstrijo", "Ziljska dolina"),
    "beljak": ("Koroška pod Avstrijo", "Ziljska dolina"),
    "völkermarkt": ("Koroška pod Avstrijo", "Podjuna"),
    "velikovec": ("Koroška pod Avstrijo", "Podjuna"),
    "bleiburg": ("Koroška pod Avstrijo", "Podjuna"),
    "pliberk": ("Koroška pod Avstrijo", "Podjuna"),
    "ferlach": ("Koroška pod Avstrijo", "Rož"),
    "borovlje": ("Koroška pod Avstrijo", "Rož"),

    # Madžarska – Porabje
    "szentgotthárd": ("Porabje pod Madžarsko", "Porabje"),
    "monošter": ("Porabje pod Madžarsko", "Porabje"),
    "felsőszölnök": ("Porabje pod Madžarsko", "Porabje"),
    "gornji senik": ("Porabje pod Madžarsko", "Porabje"),
}


def doloci_slovensko_narodno_obmocje(
    standardno_ime: str,
    kandidat: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Določi zgodovinsko slovensko narodno območje zunaj Jugoslavije.

    Vrne glavno območje, podregijo in stopnjo zanesljivosti.
    Koordinatne meje so namenoma konservativne; mejne zadetke je
    treba pred objavo preveriti z zgodovinsko karto ali literaturo.
    """

    if not je_naseljeni_kraj(kandidat):
        return None

    koda = kandidat.get("country_code")
    lat = pd.to_numeric(kandidat.get("lat"), errors="coerce")
    lon = pd.to_numeric(kandidat.get("lon"), errors="coerce")

    imena = {
        normalizirano_za_primerjavo(standardno_ime),
        normalizirano_za_primerjavo(kandidat.get("geonames_ime")),
        normalizirano_za_primerjavo(kandidat.get("toponym_name")),
    }

    for ime in imena:
        if ime in SLOVENSKA_NARODNA_OBMOCJA_ROCNO:
            obmocje, podregija = SLOVENSKA_NARODNA_OBMOCJA_ROCNO[ime]
            return {
                "narodno_obmocje": obmocje,
                "narodna_podregija": podregija,
                "zanesljivost_obmocja": "ročno pravilo po imenu",
            }

    if pd.isna(lat) or pd.isna(lon):
        return None

    lat = float(lat)
    lon = float(lon)
    regija = normalizirano_za_primerjavo(kandidat.get("regija"))

    # Italija: širši severovzhodni obmejni prostor.
    if koda == "IT" and 45.45 <= lat <= 46.70 and 12.85 <= lon <= 14.10:
        if lon >= 13.50 and lat <= 45.90:
            podregija = "Tržaško"
        elif lon >= 13.35 and lat <= 46.20:
            podregija = "Goriško"
        elif lat >= 46.25 and lon >= 13.15:
            podregija = "Kanalska dolina ali Rezija"
        else:
            podregija = "Beneška Slovenija ali zahodno obrobje"

        return {
            "narodno_obmocje": "Primorska pod Italijo",
            "narodna_podregija": podregija,
            "zanesljivost_obmocja": "koordinatno pravilo; ročno preveri",
        }

    # Avstrija: konservativno omejena južna Koroška.
    if (
        koda == "AT"
        and 46.35 <= lat <= 46.85
        and 13.55 <= lon <= 15.10
        and ("carinthia" in regija or "kärnten" in regija or not regija)
    ):
        if lon < 14.10:
            podregija = "Ziljska dolina"
        elif lon < 14.55:
            podregija = "Rož ali Celovško polje"
        else:
            podregija = "Podjuna"

        return {
            "narodno_obmocje": "Koroška pod Avstrijo",
            "narodna_podregija": podregija,
            "zanesljivost_obmocja": "koordinatno pravilo; ročno preveri",
        }

    # Madžarska: Porabje ob današnji slovensko-madžarski meji.
    if koda == "HU" and 46.75 <= lat <= 47.05 and 16.05 <= lon <= 16.45:
        return {
            "narodno_obmocje": "Porabje pod Madžarsko",
            "narodna_podregija": "Porabje",
            "zanesljivost_obmocja": "koordinatno pravilo; ročno preveri",
        }

    return None


# ============================================================
# 3. NORMALIZACIJA RAZLIČNIH ZAPISOV
#
# Leva stran je zapis v časopisu, desna stran pa standardno
# iskalno ime. Slovar lahko sproti dopolnjuješ.
# ============================================================

NORMALIZACIJE = {
    # --------------------------------------------------------
    # Države
    # --------------------------------------------------------
    "Avrstrija": "Avstrija",
    "Holandska": "Nizozemska",
    "Nizozemska/Holandija": "Nizozemska",
    "Ogrska/Madžarska": "Madžarska",
    "Rumunija": "Romunija",
    "Hrvatska": "Hrvaška",
    "Jhrvatska": "Hrvaška",
    "Estonska": "Estonija",
    "Letonska": "Latvija",
    "Lichtenstein": "Liechtenstein",
    "Maxika": "Mehika",

    "VB/Anglija": "Združeno kraljestvo",
    "Anglija": "Združeno kraljestvo",
    "Velika Britanija": "Združeno kraljestvo",

    "ZDA/Amerika": "Združene države Amerike",
    "Združene države": "Združene države Amerike",
    "Zedinjene države": "Združene države Amerike",
    "USA": "Združene države Amerike",

    "Rusija/SZ": "Sovjetska zveza",
    "Sovjetska Rusija": "Sovjetska zveza",
    "Sovjetska unija": "Sovjetska zveza",
    "Srusija": "Sovjetska zveza",

    "Abesinija": "Etiopija",
    "Avesinija": "Etiopija",
    "Perzija": "Iran",

    # --------------------------------------------------------
    # Več različic istega mesta
    # --------------------------------------------------------
    "Belgrad": "Beograd",
    "Banjaluka": "Banja Luka",
    "Benetke/venetia": "Benetke",
    "Carigrad": "Istanbul",
    "Curih": "Zürich",
    "Dunaj": "Vienna",
    "Gradec": "Graz",
    "Inomost": "Innsbruck",
    "Kiev": "Kyiv",
    "Kijev": "Kyiv",
    "Leningrad": "Saint Petersburg",
    "Petrograd": "Saint Petersburg",
    "Linc": "Linz",
    "Milano/Milan": "Milano",
    "Milan": "Milano",
    "Monakovo": "München",
    "Munchen": "München",
    "Newyork": "New York",
    "Novisad": "Novi Sad",
    "Osjek": "Osijek",
    "Peking": "Beijing",
    "Pešta": "Budimpešta",
    "Skoplje": "Skopje",
    "Tokijo": "Tokio",
    "Torino": "Turin",
    "Zader": "Zadar",

    # --------------------------------------------------------
    # Slovenski in jugoslovanski zgodovinski zapisi
    # --------------------------------------------------------
    "Dolnja Lendava": "Lendava",
    "Guštanj": "Ravne na Koroškem",
    "Marenberg": "Radlje ob Dravi",
    "Rajhenburg": "Brestanica",
    "Rihemberk": "Branik",
    "Rihenberg": "Branik",
    "Cmurek": "Mureck",
    "Karlovec": "Karlovac",
    "Peć": "Peja",
    "Reka": "Rijeka",
    "Sušak": "Sušak, Rijeka",
    "Videm": "Udine",
    "Trbiž": "Tarvisio",
    "Beljak": "Villach",
    "Beljak na Koroškem": "Villach",
    "Celovec": "Klagenfurt",
    "Solnograd": "Salzburg",

    # --------------------------------------------------------
    # Poenotenje slovenskih zapisov
    # --------------------------------------------------------
    "Gornji grad": "Gornji Grad",
    "Grahovo pri cerknici": "Grahovo pri Cerknici",
    "Kamna gorica": "Kamna Gorica",
    "Kranjska gora": "Kranjska Gora",
    "Novo mesto": "Novo Mesto",
    "Rimske toplice": "Rimske Toplice",
    "Slovenjgradec": "Slovenj Gradec",
    "Slovenjske Konjice": "Slovenske Konjice",
    "Šostanj": "Šoštanj",
    "Topolščica": "Topolšica",
    "Trižič": "Tržič",
    "Tržič na Gorenjskem": "Tržič",
    "Višnja gora": "Višnja Gora",
    "Zidani most": "Zidani Most",

    # --------------------------------------------------------
    # Očitne tipkarske ali OCR-napake
    # --------------------------------------------------------
    "Crknica": "Cerknica",
    "Mostrana": "Mojstrana",
    "Ptuja": "Ptuj",
    "RadensKranj": "Kranj",
    "Tržil": "Tržič",
    "Zagoreje ob Savi": "Zagorje ob Savi",
}


# ============================================================
# 4. POSEBNA OBMOČJA
#
# Ta imena se ne pripišejo avtomatično eni današnji državi.
# Hranijo se ločeno, saj so celine, nadnacionalne regije,
# zgodovinske države ali zgodovinske pokrajine.
# ============================================================

POSEBNA_OBMOCJA = {
    "Afrika": "celina",
    "Azija": "celina",
    "Evropa": "celina",
    "Severna Amerika": "celina",
    "Južna Amerika": "celina",
    "Amerika": "nejasna celinska ali državna oznaka",
    "Arabija": "zgodovinska oziroma nadnacionalna regija",
    "Balkan": "nadnacionalna regija",
    "Banat": "zgodovinska regija",
    "Bačka": "zgodovinska regija",
    "Besarabija": "zgodovinska regija",
    "Dalmacija": "zgodovinska regija",
    "Galicija": "zgodovinska regija",
    "Istra": "zgodovinska čezmejna regija",
    "Koroška": "zgodovinska čezmejna regija",
    "Štajerska": "zgodovinska čezmejna regija",
    "Srem": "zgodovinska regija",
    "Slavonija": "zgodovinska regija",
    "Vojvodina": "zgodovinska oziroma upravna regija",
    "Makedonija": "zgodovinska oziroma geografska regija",
    "Mala Azija": "zgodovinska geografska regija",
    "Podonavje": "nadnacionalna regija",
    "Porenje": "geografska regija",
    "Porurje": "industrijska regija",
    "Bavarska": "upravna oziroma zgodovinska regija",
    "Alzacija": "upravna oziroma zgodovinska regija",
    "Flandrija": "upravna oziroma zgodovinska regija",
    "Grenlandija": "avtonomno ozemlje",
    "Grönland": "avtonomno ozemlje",
    "Grönlandija": "avtonomno ozemlje",
    "Tibet": "zgodovinska oziroma avtonomna regija",
    "Kamčatka": "geografska regija",
    "Korzika": "otok oziroma upravna regija",
    "Kreta": "otok oziroma regija",
    "Sicilija": "otok oziroma upravna regija",

    "Avstro-Ogrska": "zgodovinska država",
    "Avstro Ogrska": "zgodovinska država",
    "Češkoslovaška": "zgodovinska država",
    "Jugoslavija": "zgodovinska država",
    "Kraljevina SHS": "zgodovinska država",
    "država SHS": "zgodovinska država",
    "Sovjetska zveza": "zgodovinska država",

    "Julijska Krajina": "zgodovinska čezmejna regija",
    "Julijska Benečija": "zgodovinska čezmejna regija",
    "Julijska Krajina/Julijska Benečija": "zgodovinska čezmejna regija",

    # Slovenske pokrajine, ki jih lahko analiziraš ločeno
    "Bela Krajina": "slovenska pokrajina",
    "Dolenjska": "slovenska pokrajina",
    "Gorenjska": "slovenska pokrajina",
    "Goriška": "slovenska pokrajina",
    "Notranjska": "slovenska pokrajina",
    "Prekmurje": "slovenska pokrajina",
    "Primorska": "slovenska pokrajina",
    "Prlekija": "slovenska pokrajina",
    "Slovenske gorice": "slovenska pokrajina",
    "Savinjska dolina": "slovenska pokrajina",
    "Bohinj": "slovenska pokrajina oziroma dolina",
    "Bled": "naselje oziroma območje",
    "Banjšice": "slovenska planota",
    "Kras": "čezmejna pokrajina",
    "Haloze": "slovenska pokrajina",
    "Pohorje": "slovensko pogorje",
}


# ============================================================
# 5. ROČNO POTRJENE LOKACIJE
#
# Pri domačih krajih imajo ti podatki prednost pred GeoNames.
# Sem dodajaj preverjene koordinate dvoumnih ali zgodovinskih
# krajev. Koordinate spodaj so zgolj začetni primeri; pred
# končno raziskovalno uporabo jih preveri.
# ============================================================

ROCNE_LOKACIJE = {
    "Guštanj": {
        "standardno_ime": "Ravne na Koroškem",
        "drzava": "Slovenija",
        "country_code": "SI",
        "lat": 46.543,
        "lon": 14.964,
        "opomba": "zgodovinsko ime; ročno preverjeno",
    },
    "Rajhenburg": {
        "standardno_ime": "Brestanica",
        "drzava": "Slovenija",
        "country_code": "SI",
        "lat": 45.995,
        "lon": 15.477,
        "opomba": "zgodovinsko ime; ročno preverjeno",
    },
}


# ============================================================
# 6. ZELO DVOUMNA IMENA
#
# Tudi če GeoNames najde zadetek, se ta imena ne sprejmejo
# samodejno brez dodatnega krajevnega opisa.
# ============================================================

DVOUMNA_IMENA = {
    "Bistrica",
    "Breg",
    "Brda",
    "Brdo",
    "Brod",
    "Cerklje",
    "Črna",
    "Dobrenje",
    "Gora",
    "Gorica",
    "Gradišče",
    "Javornik",
    "Kapla",
    "Kostanjevica",
    "Leskovec",
    "Log",
    "Luče",
    "Moste",
    "Podgorje",
    "Podgora",
    "Poljane",
    "Ponikva",
    "Prekopa",
    "Primskovo",
    "Rakovnik",
    "Ribnica",
    "Selnica",
    "Šent Vid",
    "Šmarjeta",
    "Stara Gora",
    "Studenci",
    "Suha",
    "Sv. Križ",
    "Trnovo",
    "Vrhpolje",
    "Zagorje",
    "Zalog",
}


# ============================================================
# 7. POMOŽNE FUNKCIJE
# ============================================================

def pocisti_besedilo(vrednost: Any) -> str:
    """Odstrani odvečne presledke in nevidne znake."""

    if pd.isna(vrednost):
        return ""

    besedilo = str(vrednost)
    besedilo = besedilo.replace("\ufeff", "")
    besedilo = besedilo.replace("\xa0", " ")
    besedilo = re.sub(r"\s+", " ", besedilo)

    return besedilo.strip()


def normaliziraj_ime(ime: str) -> str:
    """Vrne standardizirano iskalno obliko imena."""

    ime = pocisti_besedilo(ime)
    return NORMALIZACIJE.get(ime, ime)

def zaznaj_locilo(pot: Path) -> str:
    """Zazna podpičje, tabulator ali vejico."""

    kodiranja = [
        "utf-8-sig",
        "utf-8",
        "cp1250",
        "windows-1250",
        "latin-1",
    ]

    prva_vrstica = None

    for kodiranje in kodiranja:
        try:
            with pot.open(
                "r",
                encoding=kodiranje,
            ) as datoteka:
                prva_vrstica = datoteka.readline()

            break

        except UnicodeDecodeError:
            continue

    if prva_vrstica is None:
        raise ValueError(
            "Prve vrstice datoteke ni bilo mogoče prebrati."
        )

    stevila = {
        ";": prva_vrstica.count(";"),
        "\t": prva_vrstica.count("\t"),
        ",": prva_vrstica.count(","),
    }

    locilo = max(stevila, key=stevila.get)

    if stevila[locilo] == 0:
        raise ValueError(
            "Ločila ni bilo mogoče zaznati. "
            "Datoteka mora vsebovati stolpca kraj in omembe."
        )

    return locilo

def preberi_vhodno_datoteko(pot: Path) -> pd.DataFrame:
    """Prebere, očisti in združi vhodne podatke."""

    if not pot.exists():
        raise FileNotFoundError(
            f"Vhodna datoteka ne obstaja: {pot}"
        )

    locilo = zaznaj_locilo(pot)
    print(f"Zaznano ločilo: {repr(locilo)}")

    kodiranja = [
        "utf-8-sig",
        "utf-8",
        "cp1250",
        "windows-1250",
        "latin-1",
    ]

    df = None

    for kodiranje in kodiranja:
        try:
            df = pd.read_csv(
                pot,
                sep=locilo,
                encoding=kodiranje,
            )

            print(f"Uporabljeno kodiranje: {kodiranje}")
            break

        except UnicodeDecodeError:
            continue

    if df is None:
        raise ValueError(
            "Datoteke ni bilo mogoče prebrati. "
            "Poskusi jo v Excelu ali VS Code shraniti kot UTF-8 CSV."
        )

    df.columns = [
        pocisti_besedilo(stolpec).lower()
        for stolpec in df.columns
    ]

    zahtevani = {"kraj", "omembe"}

    if not zahtevani.issubset(df.columns):
        raise KeyError(
            "Pričakovana sta stolpca 'kraj' in 'omembe'. "
            f"Najdeni stolpci: {list(df.columns)}"
        )

    df = df[["kraj", "omembe"]].copy()

    df["izvirno_ime"] = df["kraj"].apply(
        pocisti_besedilo
    )

    df["standardno_ime"] = df["izvirno_ime"].apply(
        normaliziraj_ime
    )

    df["omembe"] = pd.to_numeric(
        df["omembe"],
        errors="coerce",
    ).fillna(0).astype(int)

    df = df[
        (df["izvirno_ime"] != "")
        & (df["omembe"] > 0)
    ].copy()

    df = (
        df.groupby("standardno_ime", as_index=False)
        .agg(
            omembe=("omembe", "sum"),
            izvirne_oblike=(
                "izvirno_ime",
                lambda x: " | ".join(
                    sorted(set(x))
                ),
            ),
        )
    )

    return (
        df.sort_values("standardno_ime")
        .reset_index(drop=True)
    )

def nalozi_predpomnilnik() -> dict[str, Any]:
    """Prebere že shranjene odgovore GeoNames."""

    if not PREDPOMNILNIK.exists():
        return {}

    try:
        with PREDPOMNILNIK.open("r", encoding="utf-8") as datoteka:
            return json.load(datoteka)
    except (json.JSONDecodeError, OSError):
        print("Opozorilo: predpomnilnika ni bilo mogoče prebrati.")
        return {}


def shrani_predpomnilnik(cache: dict[str, Any]) -> None:
    """Varno shrani predpomnilnik."""

    zacasna = PREDPOMNILNIK.with_suffix(".tmp")

    with zacasna.open("w", encoding="utf-8") as datoteka:
        json.dump(
            cache,
            datoteka,
            ensure_ascii=False,
            indent=2,
        )

    zacasna.replace(PREDPOMNILNIK)


def poisci_geonames(
    iskalno_ime: str,
    cache: dict[str, Any],
    seja: requests.Session,
) -> tuple[list[dict[str, Any]], str | None, bool]:
    """
    Vrne:
    - seznam zadetkov,
    - morebitno napako,
    - podatek, ali je bil uporabljen predpomnilnik.
    """

    kljuc = iskalno_ime.casefold()

    if kljuc in cache:
        zapis = cache[kljuc]
        return (
            zapis.get("zadetki", []),
            zapis.get("napaka"),
            True,
        )

    params = {
        "q": iskalno_ime,
        "maxRows": STEVILO_KANDIDATOV,
        "username": GEONAMES_USERNAME,
        "lang": "sl",
        "style": "FULL",
        "type": "json",
        "isNameRequired": "true",
        "orderby": "relevance",
    }

    zadnja_napaka = None

    for poskus in range(1, 4):
        try:
            odgovor = seja.get(
                GEONAMES_URL,
                params=params,
                timeout=30,
            )

            if odgovor.status_code == 429:
                zadnja_napaka = "GeoNames je omejil število zahtevkov (HTTP 429)"
                time.sleep(5 * poskus)
                continue

            odgovor.raise_for_status()
            podatki = odgovor.json()

            if "status" in podatki:
                zadnja_napaka = podatki["status"].get(
                    "message",
                    "Neznana napaka GeoNames",
                )
                break

            zadetki = podatki.get("geonames", [])

            cache[kljuc] = {
                "iskalno_ime": iskalno_ime,
                "zadetki": zadetki,
                "napaka": None,
            }

            shrani_predpomnilnik(cache)
            time.sleep(ZAMIK_MED_ZAHTEVAMI)

            return zadetki, None, False

        except requests.exceptions.Timeout:
            zadnja_napaka = "časovna prekoračitev"
            time.sleep(3 * poskus)

        except requests.exceptions.RequestException as napaka:
            zadnja_napaka = str(napaka)
            time.sleep(3 * poskus)

        except ValueError as napaka:
            zadnja_napaka = f"neveljaven odgovor JSON: {napaka}"
            break

    cache[kljuc] = {
        "iskalno_ime": iskalno_ime,
        "zadetki": [],
        "napaka": zadnja_napaka,
    }

    shrani_predpomnilnik(cache)
    return [], zadnja_napaka, False


def pretvori_geonames_zadetek(
    zadetek: dict[str, Any],
    vrstni_red: int,
) -> dict[str, Any]:
    """Pretvori surov zadetek GeoNames v enotno obliko."""

    return {
        "vrstni_red_kandidata": vrstni_red,
        "geonames_id": zadetek.get("geonameId"),
        "geonames_ime": zadetek.get("name"),
        "toponym_name": zadetek.get("toponymName"),
        "drzava": zadetek.get("countryName"),
        "country_code": zadetek.get("countryCode"),
        "lat": pd.to_numeric(zadetek.get("lat"), errors="coerce"),
        "lon": pd.to_numeric(zadetek.get("lng"), errors="coerce"),
        "feature_class": zadetek.get("fcl"),
        "feature_code": zadetek.get("fcode"),
        "regija": zadetek.get("adminName1"),
        "okrozje": zadetek.get("adminName2"),
        "prebivalstvo": zadetek.get("population", 0) or 0,
    }


def je_naseljeni_kraj(kandidat: dict[str, Any]) -> bool:
    """GeoNamesov razred P pomeni naseljeni kraj."""

    return kandidat.get("feature_class") == "P"


def je_drzava(kandidat: dict[str, Any]) -> bool:
    """Prepozna zadetek, ki predstavlja državo."""

    return (
        kandidat.get("feature_class") == "A"
        and kandidat.get("feature_code") in {"PCLI", "PCL", "PCLD", "PCLS"}
    )


def normalizirano_za_primerjavo(vrednost: Any) -> str:
    """Poenoti ime za varno primerjavo kandidatov."""

    return pocisti_besedilo(vrednost).casefold()


def kandidat_se_ujema_z_imenom(
    standardno_ime: str,
    kandidat: dict[str, Any],
) -> bool:
    """Preveri natančno ujemanje standardnega in GeoNames imena."""

    cilj = normalizirano_za_primerjavo(standardno_ime)

    imena = {
        normalizirano_za_primerjavo(kandidat.get("geonames_ime")),
        normalizirano_za_primerjavo(kandidat.get("toponym_name")),
    }

    return cilj in imena


def oceni_kandidata(
    standardno_ime: str,
    kandidat: dict[str, Any],
) -> int:
    """
    Rangira kandidata brez avtomatičnega favoriziranja Jugoslavije.

    Največ šteje:
    - natančno ujemanje imena,
    - ali gre za državo oziroma naseljeni kraj,
    - velikost naselja,
    - vrstni red GeoNames.

    Majhen bonus za jugoslovanski prostor se uporabi samo kot zadnje
    ločilo med sicer primerljivimi kandidati. Tako zaselek z imenom
    Pariz, Švica ali Poljska ne premaga dejanskega tujega kraja/države.
    """

    ocena = 0
    natancno = kandidat_se_ujema_z_imenom(standardno_ime, kandidat)

    if natancno:
        ocena += 120

    if je_drzava(kandidat):
        # Pri imenih držav (npr. Švica, Poljska) mora imeti natančen
        # državni zadetek absolutno prednost pred istoimenskim zaselkom.
        ocena += 160 if natancno else 20

    if je_naseljeni_kraj(kandidat):
        ocena += 70

    prebivalstvo = int(kandidat.get("prebivalstvo") or 0)

    if prebivalstvo >= 5_000_000:
        ocena += 90
    elif prebivalstvo >= 1_000_000:
        ocena += 80
    elif prebivalstvo >= 250_000:
        ocena += 65
    elif prebivalstvo >= 100_000:
        ocena += 55
    elif prebivalstvo >= 25_000:
        ocena += 40
    elif prebivalstvo >= 5_000:
        ocena += 25
    elif prebivalstvo > 0:
        ocena += 10

    # Le blag regionalni bonus; ne sme preglasiti pravega tujega mesta.
    if kandidat.get("country_code") in JUGOSLOVANSKE_KODE:
        ocena += 8

    # GeoNames že vrača rezultate po relevantnosti. Prvi kandidati dobijo
    # majhen bonus, ki odloča le pri zelo podobnih zadetkih.
    vrstni_red = int(kandidat.get("vrstni_red_kandidata") or 999)
    ocena += max(0, 11 - min(vrstni_red, 11))

    return ocena


def izberi_rezultat(
    standardno_ime: str,
    kandidati: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """Izbere najverjetnejši geografski pomen imena."""

    if not kandidati:
        return None, "ni zadetkov"

    ocenjeni = []

    for kandidat in kandidati:
        kandidat = kandidat.copy()
        kandidat["natancno_ujemanje"] = kandidat_se_ujema_z_imenom(
            standardno_ime,
            kandidat,
        )
        kandidat["ocena"] = oceni_kandidata(standardno_ime, kandidat)
        ocenjeni.append(kandidat)

    ocenjeni.sort(
        key=lambda x: (
            x["ocena"],
            x.get("prebivalstvo") or 0,
            -(x.get("vrstni_red_kandidata") or 999),
        ),
        reverse=True,
    )

    # Natančno ujemajoča država ima prednost pred istoimenskim naseljem.
    drzavni_zadetki = [
        kandidat
        for kandidat in ocenjeni
        if kandidat.get("natancno_ujemanje") and je_drzava(kandidat)
    ]

    if drzavni_zadetki:
        return drzavni_zadetki[0], "samodejno izbrana natančno ujemajoča država"

    # Pri naseljih izbiramo predvsem med dejanskimi naseljenimi kraji.
    naselja = [k for k in ocenjeni if je_naseljeni_kraj(k)]
    izbor = naselja if naselja else ocenjeni
    najboljsi = izbor[0]

    # Domača dvoumna imena ostanejo za ročno preverjanje.
    if (
        standardno_ime in DVOUMNA_IMENA
        and najboljsi.get("country_code") in JUGOSLOVANSKE_KODE
    ):
        return None, "dvoumno domače ime"

    # Če sta najboljša kandidata skoraj izenačena in nobeden ni veliko
    # pomembnejši, odločitev prepustimo ročnemu pregledu.
    if len(izbor) > 1:
        prvi, drugi = izbor[0], izbor[1]
        razlika = prvi["ocena"] - drugi["ocena"]
        prvo_preb = int(prvi.get("prebivalstvo") or 0)
        drugo_preb = int(drugi.get("prebivalstvo") or 0)

        if (
            razlika < 8
            and prvo_preb < max(10_000, drugo_preb * 3)
            and prvi.get("country_code") != drugi.get("country_code")
        ):
            return None, "več podobno verjetnih kandidatov"

    if najboljsi.get("country_code") in JUGOSLOVANSKE_KODE:
        status = "samodejno izbran jugoslovanski kandidat"
    else:
        status = "samodejno izbran tuji kandidat"

    return najboljsi, status


def osnovni_zapis(
    standardno_ime: str,
    izvirne_oblike: str,
    omembe: int,
) -> dict[str, Any]:
    return {
        "standardno_ime": standardno_ime,
        "izvirne_oblike": izvirne_oblike,
        "omembe": int(omembe),
    }


# ============================================================
# 8. GLAVNA OBDELAVA
# ============================================================

def main() -> None:
    if GEONAMES_USERNAME == "TVOJE_GEONAMES_UPORABNISKO_IME":
        raise ValueError(
            "V vrstico GEONAMES_USERNAME vpiši svoje uporabniško ime GeoNames."
        )

    print("Berem vhodne podatke ...")
    df = preberi_vhodno_datoteko(VHODNA_DATOTEKA)

    print(f"Število različnih normaliziranih imen: {len(df)}")

    cache = nalozi_predpomnilnik()
    seja = requests.Session()

    seja.headers.update({
        "User-Agent": (
            "geografija-porocanja-diplomska/1.0 "
            f"(GeoNames uporabnik: {GEONAMES_USERNAME})"
        )
    })

    domaci: list[dict[str, Any]] = []
    tuji_posamezni: list[dict[str, Any]] = []
    posebna_obmocja: list[dict[str, Any]] = []
    narodna_obmocja: list[dict[str, Any]] = []
    rocni_pregled: list[dict[str, Any]] = []
    vsi_rezultati: list[dict[str, Any]] = []
    vsi_kandidati: list[dict[str, Any]] = []

    skupno = len(df)

    for indeks, vrstica in df.iterrows():
        standardno_ime = vrstica["standardno_ime"]
        izvirne_oblike = vrstica["izvirne_oblike"]
        omembe = int(vrstica["omembe"])

        osnovni = osnovni_zapis(
            standardno_ime,
            izvirne_oblike,
            omembe,
        )

        print(f"[{indeks + 1}/{skupno}] {standardno_ime}")

        # ----------------------------------------------------
        # A. Posebna območja
        # ----------------------------------------------------
        if standardno_ime in POSEBNA_OBMOCJA:
            zapis = {
                **osnovni,
                "kategorija": POSEBNA_OBMOCJA[standardno_ime],
                "status": "ločena prostorska kategorija",
            }

            posebna_obmocja.append(zapis)
            vsi_rezultati.append({
                **zapis,
                "skupina": "posebno območje",
            })

            print(f"  → posebno območje: {zapis['kategorija']}")
            continue

        # ----------------------------------------------------
        # B. Ročno potrjene lokacije
        # ----------------------------------------------------
        if standardno_ime in ROCNE_LOKACIJE:
            r = ROCNE_LOKACIJE[standardno_ime]

            zapis = {
                **osnovni,
                "geonames_ime": r["standardno_ime"],
                "drzava": r["drzava"],
                "country_code": r["country_code"],
                "lat": r["lat"],
                "lon": r["lon"],
                "feature_class": "P",
                "feature_code": None,
                "regija": None,
                "geonames_id": None,
                "status": "ročno potrjeno",
                "opomba": r.get("opomba"),
            }

            domaci.append(zapis)
            vsi_rezultati.append({
                **zapis,
                "skupina": "domači/jugoslovanski kraj",
            })

            print("  ✓ ročno potrjeno")
            continue

        # ----------------------------------------------------
        # C. GeoNames
        # ----------------------------------------------------
        surovi_zadetki, napaka, iz_cache = poisci_geonames(
            standardno_ime,
            cache,
            seja,
        )

        if iz_cache:
            print("  ↳ uporabljen predpomnilnik")

        kandidati = [
            pretvori_geonames_zadetek(zadetek, vrstni_red)
            for vrstni_red, zadetek in enumerate(surovi_zadetki, start=1)
        ]

        for kandidat in kandidati:
            vsi_kandidati.append({
                **osnovni,
                **kandidat,
            })

        if napaka:
            zapis = {
                **osnovni,
                "razlog": f"napaka GeoNames: {napaka}",
                "predlagani_kandidati": "",
            }

            rocni_pregled.append(zapis)
            vsi_rezultati.append({
                **osnovni,
                "skupina": "ročni pregled",
                "status": zapis["razlog"],
            })

            print(f"  ✗ {napaka}")
            continue

        izbran, status_izbire = izberi_rezultat(
            standardno_ime,
            kandidati,
        )

        if izbran is None:
            predlogi = " | ".join(
                f"{k.get('geonames_ime')}, "
                f"{k.get('regija') or ''}, "
                f"{k.get('drzava') or ''} "
                f"[{k.get('lat')}, {k.get('lon')}]"
                for k in kandidati[:5]
            )

            zapis = {
                **osnovni,
                "razlog": status_izbire,
                "predlagani_kandidati": predlogi,
            }

            rocni_pregled.append(zapis)
            vsi_rezultati.append({
                **osnovni,
                "skupina": "ročni pregled",
                "status": status_izbire,
            })

            print(f"  ? {status_izbire}")
            continue

        koda = izbran.get("country_code")

        # ----------------------------------------------------
        # D. Slovenska narodna območja zunaj Jugoslavije
        # ----------------------------------------------------
        narodno = doloci_slovensko_narodno_obmocje(
            standardno_ime,
            izbran,
        )

        if narodno is not None:
            zapis = {
                **osnovni,
                "geonames_ime": izbran.get("geonames_ime"),
                "drzava": izbran.get("drzava"),
                "country_code": koda,
                "lat": izbran.get("lat"),
                "lon": izbran.get("lon"),
                "feature_class": izbran.get("feature_class"),
                "feature_code": izbran.get("feature_code"),
                "regija": izbran.get("regija"),
                "okrozje": izbran.get("okrozje"),
                "geonames_id": izbran.get("geonames_id"),
                **narodno,
                "status": status_izbire,
                "opomba": (
                    "Slovensko narodno območje zunaj meja "
                    "Kraljevine Jugoslavije; pred končno uporabo "
                    "preveri zgodovinsko pripadnost kraja."
                ),
            }

            narodna_obmocja.append(zapis)
            vsi_rezultati.append({
                **zapis,
                "skupina": "slovensko narodno območje zunaj Jugoslavije",
            })

            print(
                f"  ◇ {narodno['narodno_obmocje']} – "
                f"{narodno['narodna_podregija']}"
            )
            continue

        # ----------------------------------------------------
        # E. Slovenija ali nekdanja Jugoslavija
        # ----------------------------------------------------
        if koda in JUGOSLOVANSKE_KODE:
            zapis = {
                **osnovni,
                "geonames_ime": izbran.get("geonames_ime"),
                "drzava": izbran.get("drzava"),
                "country_code": koda,
                "lat": izbran.get("lat"),
                "lon": izbran.get("lon"),
                "feature_class": izbran.get("feature_class"),
                "feature_code": izbran.get("feature_code"),
                "regija": izbran.get("regija"),
                "okrozje": izbran.get("okrozje"),
                "geonames_id": izbran.get("geonames_id"),
                "status": "samodejno; preveriti pred končno analizo",
                "opomba": status_izbire,
            }

            domaci.append(zapis)
            vsi_rezultati.append({
                **zapis,
                "skupina": "domači/jugoslovanski kraj",
            })

            print(
                f"  ✓ {izbran.get('geonames_ime')}, "
                f"{izbran.get('drzava')}"
            )

        # ----------------------------------------------------
        # F. Tujina
        # ----------------------------------------------------
        else:
            zapis = {
                **osnovni,
                "geonames_ime": izbran.get("geonames_ime"),
                "drzava": izbran.get("drzava"),
                "country_code": koda,
                "lat": izbran.get("lat"),
                "lon": izbran.get("lon"),
                "feature_class": izbran.get("feature_class"),
                "feature_code": izbran.get("feature_code"),
                "regija": izbran.get("regija"),
                "okrozje": izbran.get("okrozje"),
                "geonames_id": izbran.get("geonames_id"),
                "status": status_izbire,
                "opomba": "Tuji zapis je ohranjen kot posamezna lokacija; država ni agregirana.",
            }

            if not koda or not izbran.get("drzava"):
                rocni_pregled.append({
                    **osnovni,
                    "razlog": "države ni bilo mogoče določiti",
                    "predlagani_kandidati": str(
                        izbran.get("geonames_ime") or ""
                    ),
                })

                vsi_rezultati.append({
                    **zapis,
                    "skupina": "ročni pregled",
                })

                print("  ? država ni določena")
                continue

            tuji_posamezni.append(zapis)
            vsi_rezultati.append({
                **zapis,
                "skupina": "tuji kraj ali država",
            })

            print(f"  → {izbran.get('drzava')}")

    # ========================================================
    # 9. IZDELAVA TABEL
    # ========================================================

    domaci_df = pd.DataFrame(domaci)
    tuji_df = pd.DataFrame(tuji_posamezni)
    posebna_df = pd.DataFrame(posebna_obmocja)
    narodna_df = pd.DataFrame(narodna_obmocja)
    pregled_df = pd.DataFrame(rocni_pregled)
    vsi_df = pd.DataFrame(vsi_rezultati)
    kandidati_df = pd.DataFrame(vsi_kandidati)

    # Tuji zapisi ostanejo posamezne lokacije z lastnimi koordinatami.
    # Ne seštevamo jih po državi, ker bo zgodovinska država določena
    # pozneje s prostorskim spojem (Spatial Join) na sloj CShapes.
    if not tuji_df.empty:
        tuji_df = tuji_df.sort_values(
            ["omembe", "drzava", "standardno_ime"],
            ascending=[False, True, True],
        )

    if not domaci_df.empty:
        domaci_df = domaci_df.sort_values(
            ["omembe", "drzava", "standardno_ime"],
            ascending=[False, True, True],
        )

    if not posebna_df.empty:
        posebna_df = posebna_df.sort_values(
            ["omembe", "standardno_ime"],
            ascending=[False, True],
        )

    if not narodna_df.empty:
        narodna_df = narodna_df.sort_values(
            ["narodno_obmocje", "narodna_podregija", "omembe"],
            ascending=[True, True, False],
        )

    if not pregled_df.empty:
        pregled_df = pregled_df.sort_values(
            ["omembe", "standardno_ime"],
            ascending=[False, True],
        )

    # ========================================================
    # 10. SHRANJEVANJE
    # ========================================================

    nastavitve_csv = {
        "sep": ";",
        "index": False,
        "encoding": "utf-8-sig",
    }

    domaci_df.to_csv(DOMACI_KRAJI_CSV, **nastavitve_csv)
    tuji_df.to_csv(TUJI_KRAJI_CSV, **nastavitve_csv)
    posebna_df.to_csv(POSEBNA_OBMOCJA_CSV, **nastavitve_csv)
    narodna_df.to_csv(SLOVENSKA_NARODNA_OBMOCJA_CSV, **nastavitve_csv)
    pregled_df.to_csv(ROCNI_PREGLED_CSV, **nastavitve_csv)
    vsi_df.to_csv(VSI_REZULTATI_CSV, **nastavitve_csv)
    kandidati_df.to_csv(KANDIDATI_CSV, **nastavitve_csv)

    # ========================================================
    # 11. POVZETEK
    # ========================================================

    print()
    print("=" * 60)
    print("OBDELAVA JE KONČANA")
    print("=" * 60)

    print(f"Domači in jugoslovanski kraji: {len(domaci_df)}")
    print(f"Tuji kraji z koordinatami: {len(tuji_df)}")
    print(f"Posebna zgodovinska/regionalna območja: {len(posebna_df)}")
    print(f"Slovenska narodna območja zunaj Jugoslavije: {len(narodna_df)}")
    print(f"Zapisi za ročni pregled: {len(pregled_df)}")

    if not domaci_df.empty:
        print(
            "Skupno omemb domačih/jugoslovanskih krajev: "
            f"{domaci_df['omembe'].sum()}"
        )

    if not tuji_df.empty:
        print(
            "Skupno omemb tujih krajev/lokacij: "
            f"{tuji_df['omembe'].sum()}"
        )

    print()
    print("Datoteke so shranjene v:")
    print(MAPA_REZULTATOV)

    print()
    print(f"- {DOMACI_KRAJI_CSV.name}")
    print(f"- {TUJI_KRAJI_CSV.name}")
    print(f"- {POSEBNA_OBMOCJA_CSV.name}")
    print(f"- {SLOVENSKA_NARODNA_OBMOCJA_CSV.name}")
    print(f"- {ROCNI_PREGLED_CSV.name}")
    print(f"- {VSI_REZULTATI_CSV.name}")
    print(f"- {KANDIDATI_CSV.name}")


if __name__ == "__main__":
    main()