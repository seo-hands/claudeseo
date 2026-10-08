# Support request: SERP API live/regular returns two different result sets for identical parameters (google.de)

**To:** DataForSEO Support  
**Subject:** Google Organic SERP `live/regular` (google.de, location 2276): about half of the responses are not the real first page

Hello,

we collect Google Organic SERPs for German travel keywords and see that the endpoint returns, for byte-identical request parameters, one of two completely different result sets. One of them matches what a browser shows on google.de; the other one does not appear in the browser at all. We would like to understand the cause and how to request only the genuine first page.

## Request

```
POST https://api.dataforseo.com/v3/serp/google/organic/live/regular
[{"keyword": "<keyword>", "location_code": 2276, "language_code": "de", "se_domain": "google.de", "device": "desktop", "depth": 10}]
```

All tasks returned `status_code 20000`, `pages_count 1`, the same `check_url` and no `spell` correction. Only the keyword changed between requests.

## What we observe

- We requested the same 100 keywords twice on 2026-10-08, about 13 minutes apart (11:30 and 11:44 UTC). For **60 of 100 keywords the two responses share no organic URL at all**; for 30 keywords they share 7–9 URLs. There is almost nothing in between, so each response is one of two distinct versions rather than normal ranking fluctuation.
- The unexpected version made up 56 of 100 responses in the first run and 48 of 100 in the second run, i.e. roughly half.
- An earlier collection for another country on 2026-10-07 (same parameters, 78 keywords) contains 33 responses with the same signs.
- For the main keyword `ägypten urlaub` three of four requests on the same day returned the unexpected version.

## Signs of the unexpected version

| | Expected version | Unexpected version |
|---|---|---|
| `se_results_count` | about 100–200 | thousands to ~100,000 |
| `item_types` | contains `related_searches` | no `related_searches` |
| Organic results | category/landing pages of large tour operators, official sites | deep paginated URLs (`?page=3`, `?page=11`), forum threads, YouTube, articles from 2011–2014, small affiliate sites |
| Browser (google.de, gl=de) | matches | never seen |

## Examples (same parameters, both versions)

### `ägypten urlaub`

| | Unexpected version | Expected version |
|---|---|---|
| task id | `10081130-2727-0121-0000-b081cbb4f4f8` | `10081143-2727-0121-0000-ca34f05ae2d8` |
| API datetime | 2026-10-08 11:30:53 +00:00 | 2026-10-08 11:43:31 +00:00 |
| se_results_count | 97900 | 160 |
| related_searches in item_types | no | yes |
| organic URLs in common | 0 | |

Unexpected version, organic results:

1. https://www.vtours.com/de/reiseziele/%C3%A4gypten/?page=3
2. https://www.holidaycheck.de/dh/hotels-aegypten/1cf3cc56-b513-3cac-a288-f4a64a14e4ff?accotype=condo
3. https://www.urlaub-kassel.de/online-buchen/pauschalreise/buchen/aegypten/?departures=
4. https://www.youtube.com/watch?v=QlSTk1Cp5F8
5. https://www.pauschalreisecheck.de/aegypten-urlaub-buchen/?srsltid=AU7gw4WXlIydsQpIL35WANdLzc9uOK2M5HV9SXOSBnzYBCh54L2JcCPx
6. https://www.urlaub-dortmund.de/online-buchen/pauschalreise/buchen/aegypten
7. https://www.holidaycheck.de/foren/aegypten-48/erster-aegypten-urlaub-einige-ungeklaerte-fragen-148719
8. https://www.urlaubsangebote.de/online-buchen/pauschalreise/buchen/aegypten/?portal=fkb
9. https://www.momondo.de/hotels/aagypten

Expected version, organic results:

1. https://www.sonnenklar.tv/pauschalreise/aegypten.html
2. https://www.holidaycheck.de/urlaub/aegypten
3. https://www.lidl-reisen.de/urlaub/aegypten
4. https://www.schauinsland-reisen.de/urlaubsziele/aegypten
5. https://www.lmx.de/aegypten-urlaub/
6. https://www.ab-ins-blaue.de/urlaub/aegypten.html
7. https://coraltravel.de/urlaub/aegypten/
8. https://www.loveholidays.com/de/urlaub/aegypten/

### `pauschalreise ägypten`

| | Unexpected version | Expected version |
|---|---|---|
| task id | `10081130-2727-0121-0000-c38f94b30ade` | `10081143-2727-0121-0000-8251c8af2947` |
| API datetime | 2026-10-08 11:30:56 +00:00 | 2026-10-08 11:44:01 +00:00 |
| se_results_count | 50400 | 106 |
| related_searches in item_types | no | yes |
| organic URLs in common | 0 | |

Unexpected version, organic results:

1. https://www.adacreisen.de/urlaub/aegypten/el-gouna
2. https://www.sonnenklar.tv/ort/Rundreise_Kairo_Baden/Hurghada.html
3. https://www.loveholidays.com/at/urlaub/last-minute-aegypten/
4. https://www.expedia.de/lp/b/urlaub/pauschalreisen/afrika/aegypten/marsa-alam-queseir
5. https://www.holidayplatz.de/urlaub/aegypten/ab-bremen
6. https://www.urlaubsangebote.de/online-buchen/pauschalreise/buchen/aegypten/?portal=fdh
7. https://www.adacreisen.de/urlaub/aegypten/soma-bay
8. https://www.urlaub-duesseldorf.de/online-buchen/pauschalreise/buchen/aegypten/?departures=
9. https://www.urlaub-kassel.de/online-buchen/pauschalreise/buchen/aegypten

Expected version, organic results:

1. https://www.schauinsland-reisen.de/urlaubsziele/aegypten
2. https://www.sonnenklar.tv/pauschalreise/aegypten.html
3. https://www.rewe-reisen.de/urlaubsziele/afrika/aegypten/pauschalreisen.html
4. https://www.dertour.de/pauschalreisen/aegypten
5. https://www.holidaycheck.de/tp/pauschalreisen-aegypten/1cf3cc56-b513-3cac-a288-f4a64a14e4ff
6. https://www.lidl-reisen.de/pauschalreisen/aegypten
7. https://www.oeger.de/pauschalreisen/aegypten-urlaub/
8. https://holidays.eurowings.com/de-de/pauschalreisen/aegypten.html
9. https://www.restplatzboerse.com/urlaub/aegypten/

### `ägypten reisewarnung`

| | Unexpected version | Expected version |
|---|---|---|
| task id | `10081130-2727-0121-0000-67c548bb156a` | `10081143-2727-0121-0000-038bc180592d` |
| API datetime | 2026-10-08 11:30:57 +00:00 | 2026-10-08 11:43:57 +00:00 |
| se_results_count | 4390 | 114 |
| related_searches in item_types | no | yes |
| organic URLs in common | 0 | |

Unexpected version, organic results:

1. https://aegyptenkulturreisen.de/blog/agypten-urlaub-reisewarnung
2. https://www.borkenerzeitung.de/welt/in-ausland/panorama/Urlaub-in-Tuerkei-und-Aegypten-Reiseverband-sieht-kein-Risiko-730134.html
3. https://www.hoerzu.de/ratgeber/aufgepasst-teil-reisewarnung-fuer-aegypten---das-musst-du-wissen/
4. https://www.spiegel.de/reise/aktuell/aegypten-was-reisende-jetzt-beachten-muessen-a-742972.html
5. https://www.n-tv.de/mediathek/videos/politik/Unruhen-belasten-Tourismusbranche-article10920061.html
6. https://www.welt.de/reise/Fern/article125249135/Aegypten-Auswaertiges-Amt-warnt-dringend-vor-Sinai-Reisen.html
7. https://www.tagesspiegel.de/gesellschaft/reise/plan-b-in-der-schublade-2542003.html
8. https://www.fuldaerzeitung.de/fulda/auswaertiges-erweitert-reisewarnung-ganz-aegypten-13736235.html

Expected version, organic results:

1. https://www.auswaertiges-amt.de/de/reiseundsicherheit/aegyptensicherheit-212622
2. https://www.bmeia.gv.at/reise-services/reiseinformation/land/aegypten
3. https://www.reiseversicherung.com/ratgeber/reisewarnung/aegypten
4. https://kairo.diplo.de/eg-de/willkommen-in-aegypten/reise-sicherheit
5. https://ecco-reisen.de/reiseziele/aegypten/aktuelle-sicherheitslage-aegypten/
6. https://www.bild.de/reisen/magazin/aegypten/wie-sicher-ist-aegypten-2026-was-familien-ueber-hurghada-marsa-alam-und-sharm-wissen-muessen/
7. https://www.urlaubsguru.de/reisemagazin/reisewarnung-aegypten-sicherheit/
8. https://www.eda.admin.ch/de/reisehinweise-fuer-aegypten

### `visum ägypten`

| | Unexpected version | Expected version |
|---|---|---|
| task id | `10081130-2727-0121-0000-2f4cfab777f1` | `10081143-2727-0121-0000-97dfe4d6f35e` |
| API datetime | 2026-10-08 11:30:51 +00:00 | 2026-10-08 11:43:54 +00:00 |
| se_results_count | 49000 | 115 |
| related_searches in item_types | no | yes |
| organic URLs in common | 0 | |

Unexpected version, organic results:

1. https://www.buch-dein-visum.de/aegypten/visum/kosten/rs
2. https://www.africatravelentry.com/de/aegypten-visum-kosten/
3. https://www.ivisa.com/de/visas/egypt
4. https://antragstellung.com/evisum-agypten/
5. https://www.youtube.com/watch?v=kko0M9ytMQA
6. https://www.botschaften-service.de/data/visaeg.html
7. https://www.visagov.com/de/agypten
8. https://e-visa-express.com/de/egypt/german
9. https://www.visamundi.co/de/reiseziele/agypten/

Expected version, organic results:

1. https://www.auswaertiges-amt.de/de/service/laender/aegypten-node
2. https://www.buch-dein-visum.de/aegypten/visum/e-visum-tourist
3. https://www.buch-dein-visum.de/aegypten/service/fragen-und-antworten
4. https://kairo.diplo.de/eg-de/service/05-visaeinreise/1434288-1434288
5. https://www.buch-dein-visum.de/aegypten/laenderinfo/einreisebestimmungen
6. https://www.mcflight.de/aktuelles/aegypten-einreisebestimmungen-2026-digital
7. https://sonnenklartv-reisebuero.de/wesseling/aegypten/visum/
8. https://www.servisum.de/leistungsprofil/visa/visaantraege-einreisebestimmungen/aegypten/
9. https://www.skr.de/blog/aegypten-visum-und-einreisebestimmungen/

## Browser check

On 2026-10-08 we opened google.de (gl=de, German location) for three of these keywords. In all three the browser showed the expected version:

- `ägypten urlaub`: sonnenklar, holidaycheck, lidl-reisen, schauinsland, lmx, coraltravel, ab-ins-blaue, loveholidays, neckermann
- `pauschalreise ägypten`: schauinsland, sonnenklar, rewe-reisen, dertour, holidaycheck, lidl-reisen, oeger, eurowings holidays, restplatzboerse
- `ägypten reisewarnung`: auswaertiges-amt, bmeia.gv.at, reiseversicherung.com, bild, kairo.diplo.de, ecco-reisen, eda.admin.ch, urlaubsguru

The unexpected version did not appear in the browser for any of them.

## Questions

1. What is the second result set: a different Google data centre or experiment, a deeper results page, or a parsing fallback?
2. Is there a parameter that guarantees the genuine first page for `live/regular` on google.de, or a field in the response that reliably marks the other version? Right now we use `se_results_count` and the missing `related_searches` block as a heuristic.
3. Does the standard queue (`task_post`) or `live/advanced` behave differently in this respect?
4. Are the affected tasks eligible for a refund? We had to request every keyword at least twice.

We can send the complete raw responses for all 200 tasks if that helps.

Thank you,  
reisemu.de SEO team
