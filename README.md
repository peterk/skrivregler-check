# Skiss av Textkontroll för Myndigheternas skrivregler

Detta är ett utkast till ett verktyg som granskar en text mot [Myndigheternas skrivregler](https://www.isof.se/utforska/vagledningar/myndigheternas-skrivregler). 

Skrivreglerna har konverterats till markdown med hjälp av [marker](https://github.com/VikParuchuri/marker) och finns i `app/skrivregler.md`.

## Vad verktyget gör

1. **Regelbaserad kontroll** - identifierar ord och uttryck från "Svarta listan" som bör undvikas i myndighetstexter (endast delmängd just nu).
2. **LIX-värde** - beräknar textens läsbarhetsindex för att bedöma hur lättläst texten är
3. **AI-analys** - använder en språkmodell (Gemma 3 27B) för att granska texten mot Myndigheternas skrivregler och ge förslag på förbättringar. Just nu anropas en instans hos NVIDIA men modellen kan köras lokalt för den som har tillräckligt bra hårdvara. I detta test är endast ett fåtal regler implementerade (se prompten i check.py).

## Användning

Skaffa en API-nyckel för nvidias instans av Gemma 3 27B på [NVIDIA](https://build.nvidia.com/settings/api-keys). Spara API-nyckeln i en .env fil (se .env.example).

```
python app/check.py <indata-textfil> <utdata-rapportfil>
```

Resultatet innehåller:
- Sammanfattning av analysen
- Lista över specifika språkregelfel
- AI-baserad analys och rekommendationer
- Läsbarhetsvärde och tolkning
- Den ursprungliga texten

För en exempelrapport för en äldre SOU-text i `test.txt`, se `example_report.md`.

## Krav

För att använda verktyget behöver du:
- Python 3.x
- Nödvändiga beroenden (se requirements.txt)
- En API-nyckel för NVIDIA/Gemma 3 (lagras i .env-fil)


## Lärdomar

- Gemma 3 har ett kontextfönster på 128K tokens. Skrivreglerna är ca 50K tokens så troligtvis måste man dela upp analysen i delar när texterna blir längre. Det är heller inte säkert att den genererade prompten hanteras korrekt om den blir för omfattande.
- PDF för [Svarta listan](https://www.regeringen.se/contentassets/7ea8845f72304d098640272782e5bc26/svarta-listan---ord-och-fraser-som-kan-ersattas-i-forfattningssprak/) är låst för kopiering och inkonsekvent formaterad för att helt automatiskt kunna konvertera den till data. Ett utkast till konverteringsskript finns i [app/convert_svarta_listan.py](app/convert_svarta_listan.py) men kräver manuell korrigering i efterhand.
- Körtiden för analysen är rätt lång även när inferensen sker via Nvidias API.
- Gemma 3 27B är förvånansvärt bra på svenska.