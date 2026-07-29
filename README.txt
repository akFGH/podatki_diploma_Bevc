Navodila

Datoteke s končnico .csv so surovi podatki krajev in omemb razdeljeni po datotekah glede na začetnice imena časnika in leto obdelave.
S - Slovenec; SN - Slovenski narod, J - Jutro.

Vzorčili smo vsako drugo oz. tretjo izdajo časnikov izdanih v aprilu v letih 1924, 1934 in 1940.


Obdelava
V skripti geocode.py popravimo ime datoteke, da se nam prav prebere, sledi zagon skripte geocode.py, ki sproži iskanje kraja po bazi GeoNames,
ob zadetku zapiše koordinate v novo mapo rezultati. Morebitne zgrešitve ali neodločenosti katerim koordinatam ime pripada se shranijo v novo datoteko za ročni pregled,
ki ga izvedemo s pogonom skripte potrdi_kraje.py. Ponoven zagon geocode.py je potreben za sinhronizacijo podatkov v .json datoteki. 

Skripte DodajStolpce[...].py so opcijske, dodajo stolpce s fiksno vrednostjo na konec dokumenta.csv (potrebna je predhona nastavitev imen datotek v kodi).