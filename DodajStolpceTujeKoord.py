import pandas as pd

# vhodna datoteka
vhod = "tuji_kraji_s_koordinatami.csv"

# izhodna datoteka
izhod = "tujiXYJ24.csv"

# preberi CSV
df = pd.read_csv(vhod, sep=";", encoding="utf-8-sig")

# dodaj stolpce
df["casopis"] = "Jutro"
df["leto"] = 1924
df["id_vzorca"] = "Jutro24"

# shrani
df.to_csv(
    izhod,
    sep=";",
    index=False,
    encoding="utf-8-sig"
)

print("Končano.")