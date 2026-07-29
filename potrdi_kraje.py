from pathlib import Path
from time import sleep

import pandas as pd
import requests


GEONAMES_USERNAME = "anita123"

MAPA = Path(__file__).resolve().parent
REZULTATI = MAPA / "rezultati"

VHOD = REZULTATI / "za_rocni_pregled.csv"
SLOVAR = MAPA / "kraji_slovar.csv"

GEONAMES_URL = "https://secure.geonames.org/searchJSON"


STOLPCI_SLOVARJA = [
    "izvirno_ime",
    "iskalno_ime",
    "geonames_ime",
    "drzava",
    "country_code",
    "lat",
    "lon",
    "geonames_id",
    "status",
    "opomba",
]


def preberi_slovar():
    if not SLOVAR.exists():
        return pd.DataFrame(columns=STOLPCI_SLOVARJA)

    df = pd.read_csv(
        SLOVAR,
        sep=";",
        encoding="utf-8-sig",
    )

    for stolpec in STOLPCI_SLOVARJA:
        if stolpec not in df.columns:
            df[stolpec] = None

    return df[STOLPCI_SLOVARJA]


def shrani_slovar(df):
    df.to_csv(
        SLOVAR,
        sep=";",
        index=False,
        encoding="utf-8-sig",
    )


def poisci_kandidate(iskalno_ime):
    params = {
        "q": iskalno_ime,
        "maxRows": 10,
        "username": GEONAMES_USERNAME,
        "lang": "sl",
        "style": "FULL",
        "type": "json",
        "orderby": "relevance",
    }

    odgovor = requests.get(
        GEONAMES_URL,
        params=params,
        timeout=30,
    )

    if odgovor.status_code == 401:
        raise RuntimeError(
            "GeoNames je vrnil 401. Preveri uporabniško ime "
            "in omogoči Free Web Services."
        )

    odgovor.raise_for_status()

    podatki = odgovor.json()

    if "status" in podatki:
        raise RuntimeError(
            podatki["status"].get(
                "message",
                "Neznana napaka GeoNames",
            )
        )

    return podatki.get("geonames", [])


def opis_kandidata(kandidat):
    deli = [
        kandidat.get("name"),
        kandidat.get("adminName2"),
        kandidat.get("adminName1"),
        kandidat.get("countryName"),
    ]

    deli = [
        str(delcek).strip()
        for delcek in deli
        if delcek is not None and str(delcek).strip()
    ]

    return ", ".join(deli)


def main():
    pregled_df = pd.read_csv(
        VHOD,
        sep=";",
        encoding="utf-8-sig",
    )

    slovar_df = preberi_slovar()

    ze_obdelani = set(
        slovar_df["izvirno_ime"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    for _, vrstica in pregled_df.iterrows():
        kraj = str(vrstica["standardno_ime"]).strip()

        if kraj in ze_obdelani:
            print(f"– {kraj}: že v slovarju")
            continue

        iskalno_ime = kraj

        while True:
            print()
            print("=" * 70)
            print(f"Kraj: {kraj}")
            print(f"Iščem kot: {iskalno_ime}")
            print("=" * 70)

            try:
                kandidati = poisci_kandidate(iskalno_ime)

            except Exception as napaka:
                print(f"Napaka: {napaka}")
                return

            if not kandidati:
                print("Ni kandidatov.")

                novo = input(
                    "Vnesi drugo iskalno ime ali Enter za preskok: "
                ).strip()

                if novo:
                    iskalno_ime = novo
                    continue

                break

            for stevilka, kandidat in enumerate(kandidati, start=1):
                print(
                    f"{stevilka}: {opis_kandidata(kandidat)} "
                    f"[{kandidat.get('lat')}, {kandidat.get('lng')}] "
                    f"{kandidat.get('fcl')}/{kandidat.get('fcode')}"
                )

            print("0: noben kandidat ni pravilen")
            print("i: vnesi drugo iskalno ime")
            print("s: preskoči")

            izbira = input("Izbira: ").strip().lower()

            if izbira == "s":
                break

            if izbira == "i":
                novo = input("Novo iskalno ime: ").strip()

                if novo:
                    iskalno_ime = novo

                continue

            if izbira == "0":
                nova_vrstica = {
                    "izvirno_ime": kraj,
                    "iskalno_ime": iskalno_ime,
                    "geonames_ime": None,
                    "drzava": None,
                    "country_code": None,
                    "lat": None,
                    "lon": None,
                    "geonames_id": None,
                    "status": "ni razrešeno",
                    "opomba": "noben kandidat ni bil pravilen",
                }

                slovar_df = pd.concat(
                    [slovar_df, pd.DataFrame([nova_vrstica])],
                    ignore_index=True,
                )

                shrani_slovar(slovar_df)
                ze_obdelani.add(kraj)
                break

            try:
                indeks = int(izbira) - 1

                if indeks < 0 or indeks >= len(kandidati):
                    print("Neveljavna izbira.")
                    continue

            except ValueError:
                print("Vnesi številko, 0, i ali s.")
                continue

            kandidat = kandidati[indeks]

            nova_vrstica = {
                "izvirno_ime": kraj,
                "iskalno_ime": iskalno_ime,
                "geonames_ime": kandidat.get("name"),
                "drzava": kandidat.get("countryName"),
                "country_code": kandidat.get("countryCode"),
                "lat": kandidat.get("lat"),
                "lon": kandidat.get("lng"),
                "geonames_id": kandidat.get("geonameId"),
                "status": "ročno potrjeno",
                "opomba": opis_kandidata(kandidat),
            }

            slovar_df = pd.concat(
                [slovar_df, pd.DataFrame([nova_vrstica])],
                ignore_index=True,
            )

            shrani_slovar(slovar_df)
            ze_obdelani.add(kraj)

            print(
                f"✓ Shranjeno: {kraj} → "
                f"{opis_kandidata(kandidat)}"
            )

            break

        sleep(1.1)

    print()
    print(f"Slovar je shranjen v: {SLOVAR}")


if __name__ == "__main__":
    main()