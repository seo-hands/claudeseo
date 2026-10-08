# Порівняння SERP-кластеризації з кластерами за лемою

Дані: serp-raw-regular (live/regular, google.de, 78 ключів), без нових запитів до API. Кластери за лемою: 16 (не змінювалися).

Типи сторінок для методу B: last-minute, pauschalreise, all-inclusive, rundreise, hotel, info, thema, region, hub (хаб країни), other (унікальний URL). Підпис результату = (домен, тип), наприклад sonnenklar.tv|hub ≠ sonnenklar.tv|last-minute.

## Підсумок

| Метод | кластерів | з 2+ ключами | ключів у групах | пар разом | точність відносно лем | повнота відносно лем | кластерів, що зводять різні сторінки |
|---|---|---|---|---|---|---|---|
| A  soft-3, точні URL (з головним) | 56 | 7 | 29 | 95 | 26% | 12% | 3 |
| B1 домен+тип, поріг 4, soft (з головним) | 60 | 7 | 25 | 53 | 30% | 8% | 2 |
| B2 домен+тип, поріг 4, hard (з кожним) | 62 | 7 | 23 | 38 | 29% | 5% | 2 |
| B3 домен+тип, поріг 3, soft (чутливість) | 48 | 12 | 42 | 117 | 23% | 13% | 5 |
| **Лема/інтент** | **16** | 15 | 77 | 201 | – | – | 0 |

«Кластерів, що зводять різні сторінки» — кластери методу, ключі яких за розподілом лем ведуть на різні сторінки (реальні конфлікти з розподілом). Точність = частка пар ключів, які метод об'єднав і які теж в одному кластері за лемою. Повнота = частка пар за лемою, які метод теж об'єднав.

Розподіл типів сторінок у видачі: hub 132, other 131, last-minute 94, region 82, rundreise 68, pauschalreise 63, info 42, all-inclusive 40, thema 21, hotel 13

## A  soft-3, точні URL (з головним)

Кластерів 56, із них 2+ ключів: 7.

**Де метод розходиться з лемами: кластер охоплює кілька лем (кандидати на злиття)**

- [K01, K04, K07, K09, K10] türkei urlaub (K01) ; türkei urlaub günstiger (K07) ; pauschalreise türkei all inclusive (K04) ; türkei im oktober urlaub (K10) ; reise türkei buchen (K09) ; türkei strandurlaub (K01) ; türkei urlaub buchen günstig (K07) ; türkei urlaub mit flug (K01) ; günstig in die türkei fliegen (K07) ; kurzurlaub türkei (K01) ; mai urlaub türkei (K10) ; türkei reise billig (K07) ; flugreise türkei (K01)
- [K03, K04] türkei urlaub 2026 all inclusive mit flug und hotel (K03) ; pauschalreisen türkei 2026 (K04)
- [K03, K04] türkei urlaub all inclusive günstig (K03) ; pauschalreisen türkei all inclusive günstig (K04)
- [K12, K14, K15] türkei rundreise (K12) ; rundreise türkei mit badeurlaub (K15) ; türkei rundreise 7 tage (K14) ; türkei rundreise 10 tage (K14) ; 2 wochen türkei rundreise (K14)

**Кластери, що збігаються з однією лемою (2+ ключів)**

- K02: reise türkei warnung ; reise türkei sicher
- K07: türkei reise günstig ; billig türkei urlaub ; schnäppchen türkei urlaub
- K06: super last minute türkei all inclusive ; türkei reise last minute

**Леми, які метод розкидає по різних кластерах**

- K01 (Türkei Urlaub: бронювання, рік, з перель): 11 ключів у 7 кластерах методу, найбільша спільна група 5
- K02 (Türkei: Reisewarnung, aktuelle Lage, Sic): 4 ключів у 3 кластерах методу, найбільша спільна група 2
- K03 (Türkei All Inclusive): 6 ключів у 6 кластерах методу, найбільша спільна група 1
- K04 (Pauschalreise Türkei): 7 ключів у 7 кластерах методу, найбільша спільна група 1
- K05 (Side (Türkische Riviera)): 5 ключів у 5 кластерах методу, найбільша спільна група 1
- K06 (Last Minute Türkei): 8 ключів у 7 кластерах методу, найбільша спільна група 2
- K07 (Türkei Urlaub: günstig / billig / Schnäp): 8 ключів у 3 кластерах методу, найбільша спільна група 4
- K09 (Türkei Reise / Reisen: buchen, nach): 2 ключів у 2 кластерах методу, найбільша спільна група 1
- K10 (Türkei Urlaub за місяцями (Mai, Septembe): 5 ключів у 4 кластерах методу, найбільша спільна група 2
- K11 (Türkei: Einreise mit Personalausweis): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K12 (Türkei Rundreise: загальні, ціна, на вла): 4 ключів у 4 кластерах методу, найбільша спільна група 1
- K13 (Antalya / Lara): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K14 (Türkei Rundreise за тривалістю (7/10/14 ): 4 ключів у 2 кластерах методу, найбільша спільна група 3
- K15 (Türkei Rundreise + Badeurlaub): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K16 (Türkei Rundreise: Kappadokien, Istanbul,): 4 ключів у 4 кластерах методу, найбільша спільна група 1

## B1 домен+тип, поріг 4, soft (з головним)

Кластерів 60, із них 2+ ключів: 7.

**Де метод розходиться з лемами: кластер охоплює кілька лем (кандидати на злиття)**

- [K01, K07, K09, K10] türkei urlaub (K01) ; türkei urlaub günstiger (K07) ; türkei im oktober urlaub (K10) ; reise türkei buchen (K09) ; türkei strandurlaub (K01) ; türkei urlaub buchen günstig (K07) ; günstig in die türkei fliegen (K07) ; kurzurlaub türkei (K01) ; türkei reise billig (K07)
- [K03, K04] türkei urlaub 2026 all inclusive mit flug und hotel (K03) ; pauschalreisen türkei 2026 (K04)
- [K12, K14, K15] türkei rundreise (K12) ; rundreise türkei mit badeurlaub (K15) ; türkei rundreise 7 tage (K14) ; türkei rundreise 10 tage (K14) ; 2 wochen türkei rundreise (K14)
- [K06, K13] türkei antalya last minute (K13) ; super last minute türkei all inclusive (K06) ; türkei reise last minute (K06)

**Кластери, що збігаються з однією лемою (2+ ключів)**

- K02: reise türkei warnung ; reise türkei sicher
- K06: last minute türkei ; türkei last minute angebote
- K01: türkei urlaub mit flug ; flugreise türkei

**Леми, які метод розкидає по різних кластерах**

- K01 (Türkei Urlaub: бронювання, рік, з перель): 11 ключів у 8 кластерах методу, найбільша спільна група 3
- K02 (Türkei: Reisewarnung, aktuelle Lage, Sic): 4 ключів у 3 кластерах методу, найбільша спільна група 2
- K03 (Türkei All Inclusive): 6 ключів у 6 кластерах методу, найбільша спільна група 1
- K04 (Pauschalreise Türkei): 7 ключів у 7 кластерах методу, найбільша спільна група 1
- K05 (Side (Türkische Riviera)): 5 ключів у 5 кластерах методу, найбільша спільна група 1
- K06 (Last Minute Türkei): 8 ключів у 6 кластерах методу, найбільша спільна група 2
- K07 (Türkei Urlaub: günstig / billig / Schnäp): 8 ключів у 5 кластерах методу, найбільша спільна група 4
- K09 (Türkei Reise / Reisen: buchen, nach): 2 ключів у 2 кластерах методу, найбільша спільна група 1
- K10 (Türkei Urlaub за місяцями (Mai, Septembe): 5 ключів у 5 кластерах методу, найбільша спільна група 1
- K11 (Türkei: Einreise mit Personalausweis): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K12 (Türkei Rundreise: загальні, ціна, на вла): 4 ключів у 4 кластерах методу, найбільша спільна група 1
- K13 (Antalya / Lara): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K14 (Türkei Rundreise за тривалістю (7/10/14 ): 4 ключів у 2 кластерах методу, найбільша спільна група 3
- K15 (Türkei Rundreise + Badeurlaub): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K16 (Türkei Rundreise: Kappadokien, Istanbul,): 4 ключів у 4 кластерах методу, найбільша спільна група 1

## B2 домен+тип, поріг 4, hard (з кожним)

Кластерів 62, із них 2+ ключів: 7.

**Де метод розходиться з лемами: кластер охоплює кілька лем (кандидати на злиття)**

- [K01, K07, K09, K10] türkei urlaub (K01) ; türkei urlaub günstiger (K07) ; türkei im oktober urlaub (K10) ; reise türkei buchen (K09) ; türkei urlaub buchen günstig (K07) ; kurzurlaub türkei (K01) ; türkei reise billig (K07)
- [K03, K04] türkei urlaub 2026 all inclusive mit flug und hotel (K03) ; pauschalreisen türkei 2026 (K04)
- [K12, K14, K15] türkei rundreise (K12) ; rundreise türkei mit badeurlaub (K15) ; türkei rundreise 7 tage (K14) ; türkei rundreise 10 tage (K14) ; 2 wochen türkei rundreise (K14)
- [K06, K13] türkei antalya last minute (K13) ; super last minute türkei all inclusive (K06) ; türkei reise last minute (K06)

**Кластери, що збігаються з однією лемою (2+ ключів)**

- K02: reise türkei warnung ; reise türkei sicher
- K06: last minute türkei ; türkei last minute angebote
- K01: türkei urlaub mit flug ; flugreise türkei

**Леми, які метод розкидає по різних кластерах**

- K01 (Türkei Urlaub: бронювання, рік, з перель): 11 ключів у 9 кластерах методу, найбільша спільна група 2
- K02 (Türkei: Reisewarnung, aktuelle Lage, Sic): 4 ключів у 3 кластерах методу, найбільша спільна група 2
- K03 (Türkei All Inclusive): 6 ключів у 6 кластерах методу, найбільша спільна група 1
- K04 (Pauschalreise Türkei): 7 ключів у 7 кластерах методу, найбільша спільна група 1
- K05 (Side (Türkische Riviera)): 5 ключів у 5 кластерах методу, найбільша спільна група 1
- K06 (Last Minute Türkei): 8 ключів у 6 кластерах методу, найбільша спільна група 2
- K07 (Türkei Urlaub: günstig / billig / Schnäp): 8 ключів у 6 кластерах методу, найбільша спільна група 3
- K09 (Türkei Reise / Reisen: buchen, nach): 2 ключів у 2 кластерах методу, найбільша спільна група 1
- K10 (Türkei Urlaub за місяцями (Mai, Septembe): 5 ключів у 5 кластерах методу, найбільша спільна група 1
- K11 (Türkei: Einreise mit Personalausweis): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K12 (Türkei Rundreise: загальні, ціна, на вла): 4 ключів у 4 кластерах методу, найбільша спільна група 1
- K13 (Antalya / Lara): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K14 (Türkei Rundreise за тривалістю (7/10/14 ): 4 ключів у 2 кластерах методу, найбільша спільна група 3
- K15 (Türkei Rundreise + Badeurlaub): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K16 (Türkei Rundreise: Kappadokien, Istanbul,): 4 ключів у 4 кластерах методу, найбільша спільна група 1

## B3 домен+тип, поріг 3, soft (чутливість)

Кластерів 48, із них 2+ ключів: 12.

**Де метод розходиться з лемами: кластер охоплює кілька лем (кандидати на злиття)**

- [K01, K03, K04, K07, K09, K10] türkei urlaub (K01) ; türkei urlaub günstiger (K07) ; türkei urlaub all inclusive günstig (K03) ; pauschalreise türkei all inclusive (K04) ; türkei im oktober urlaub (K10) ; reise türkei buchen (K09) ; türkei strandurlaub (K01) ; türkei urlaub buchen günstig (K07) ; türkei urlaub mit flug (K01) ; günstig in die türkei fliegen (K07) ; kurzurlaub türkei (K01) ; mai urlaub türkei (K10) ; türkei reise billig (K07) ; flugreise türkei (K01)
- [K03, K04] türkei urlaub 2026 all inclusive mit flug und hotel (K03) ; pauschalreisen türkei 2026 (K04) ; pauschalreisen türkei all inclusive günstig (K04)
- [K12, K14, K15] türkei rundreise (K12) ; rundreise türkei mit badeurlaub (K15) ; türkei rundreise 7 tage (K14) ; türkei rundreise 10 tage (K14) ; 2 wochen türkei rundreise (K14)
- [K03, K04] urlaub türkei 2026 all inclusive (K03) ; pauschalreise türkei all inclusive 2026 (K04)
- [K06, K13] türkei antalya last minute (K13) ; super last minute türkei all inclusive (K06) ; türkei reise last minute (K06)
- [K06, K13] last minute urlaub türkei all inclusive (K06) ; last minute türkei antalya all inclusive (K13)
- [K01, K07] türkei urlaub 2027 (K01) ; billig türkei urlaub (K07) ; schnäppchen türkei urlaub (K07)
- [K01, K07] türkei buchen (K01) ; günstig türkei (K07)

**Кластери, що збігаються з однією лемою (2+ ключів)**

- K02: reise türkei warnung ; reise türkei sicher
- K05: urlaub side türkei ; reise türkei side
- K06: last minute türkei ; türkei last minute angebote
- K06: last minute urlaub türkei ; pauschalreisen türkei last minute

**Леми, які метод розкидає по різних кластерах**

- K01 (Türkei Urlaub: бронювання, рік, з перель): 11 ключів у 7 кластерах методу, найбільша спільна група 5
- K02 (Türkei: Reisewarnung, aktuelle Lage, Sic): 4 ключів у 3 кластерах методу, найбільша спільна група 2
- K03 (Türkei All Inclusive): 6 ключів у 6 кластерах методу, найбільша спільна група 1
- K04 (Pauschalreise Türkei): 7 ключів у 6 кластерах методу, найбільша спільна група 2
- K05 (Side (Türkische Riviera)): 5 ключів у 4 кластерах методу, найбільша спільна група 2
- K06 (Last Minute Türkei): 8 ключів у 5 кластерах методу, найбільша спільна група 2
- K07 (Türkei Urlaub: günstig / billig / Schnäp): 8 ключів у 4 кластерах методу, найбільша спільна група 4
- K09 (Türkei Reise / Reisen: buchen, nach): 2 ключів у 2 кластерах методу, найбільша спільна група 1
- K10 (Türkei Urlaub за місяцями (Mai, Septembe): 5 ключів у 4 кластерах методу, найбільша спільна група 2
- K11 (Türkei: Einreise mit Personalausweis): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K12 (Türkei Rundreise: загальні, ціна, на вла): 4 ключів у 4 кластерах методу, найбільша спільна група 1
- K13 (Antalya / Lara): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K14 (Türkei Rundreise за тривалістю (7/10/14 ): 4 ключів у 2 кластерах методу, найбільша спільна група 3
- K15 (Türkei Rundreise + Badeurlaub): 3 ключів у 3 кластерах методу, найбільша спільна група 1
- K16 (Türkei Rundreise: Kappadokien, Istanbul,): 4 ключів у 4 кластерах методу, найбільша спільна група 1
