import pandas as pd

# vhodna datoteka
vhod = "tuje_drzave.csv"

# izhodna datoteka
izhod = "tujeJ24.csv"

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