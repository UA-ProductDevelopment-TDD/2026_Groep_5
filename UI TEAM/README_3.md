# UI/UX · Bittle LEGO-sorter app

Webapp voor kinderen van 8–12 jaar: Bittle **opruimen** (sorteren op kleur) of **klaarleggen** (blokjes in volgorde klaarleggen voor een bouwopdracht).

- **Ontwerp (Figma):** https://www.figma.com/design/LFmiXsJ3FEJJODdjn9vU4D
- **App (code):** [`/docs/index.html`](../docs/index.html), één HTML-bestand, geen installatie nodig
- **Online (GitHub Pages):** `https://seppeslootmaekers.github.io/Technology-driven-design/`, nadat Pages aanstaat (zie hieronder)

## Schermen

| Flow | Schermen |
|---|---|
| Start | kies Opruimen of Klaarleggen, verbindingsstatus, stem aan/uit |
| A · Opruimen | Bezig (5 stappen + bakje op de rug) → Pauze → Klaar (teller per kleur) |
| B · Klaarleggen | Kies bouwopdracht (torentje, autootje, brug, zelf maken) → Zelf maken → Bezig (laag x van y) → Pauze → Klaar |

## Verbinding met Bittle

Via het tandwiel op het startscherm (*instellingen*):

- **Bluetooth**: Petoi BLE UART (`6E400001-…`). Werkt in Chrome of Edge, ook op Android.
- **USB-kabel**: Web Serial, 115200 baud. Werkt in Chrome of Edge op een computer.
- **Demo-modus** (standaard): een nep-Bittle in de app stuurt dezelfde berichten als de echte. Zo kunnen we testen met kinderen voor de robot klaar is.
- **Test-commando's** voor het softwareteam: knoppen voor `kbalance`, `ksit`, `khi`, `kwkF`, `kpickF`, `kputF`, `d` en een vrij invulveld. De commando's en antwoorden staan in het logvenster.

Web Bluetooth en Web Serial werken alleen op `https://` (GitHub Pages) of `localhost`, niet als je het bestand gewoon dubbelklikt.

## Berichten app ↔ Bittle (afspraak met software)

Eén tekstregel per bericht, afgesloten met een newline.

| Richting | Bericht | Betekenis |
|---|---|---|
| app → Bittle | `opruimen` | start opruimen |
| app → Bittle | `klaarleg rood wit rood wit` | leg deze kleuren klaar, in deze volgorde |
| app → Bittle | `pauze` / `verder` / `stop` | pauzeren / verdergaan / stoppen |
| Bittle → app | `stap zoeken` | ook `naderen`, `grijpen`, `brengen`, `lossen`, `neerleggen` |
| Bittle → app | `kleur rood` | welk blokje Bittle nu zoekt of pakt |
| Bittle → app | `bakje rood,wit` / `bakje leeg` | wat er in het bakje op zijn rug zit |
| Bittle → app | `gemist` | grijpen mislukt, hij probeert opnieuw |
| Bittle → app | `laag 2 4` | klaarleggen: laag 2 van 4 ligt klaar |
| Bittle → app | `klaar 5 3 4 2` | klaar; bij opruimen het aantal rood, wit, groen en blauw |

Regels die de app niet kent (bijvoorbeeld gewone Petoi-output) worden genegeerd, dus de firmware mag gewoon blijven printen.

## GitHub Pages aanzetten (één keer, door de repo-eigenaar)

1. Ga naar **Settings → Pages**.
2. Kies bij *Source* **Deploy from a branch**, dan branch **main**, map **/docs**, en klik op **Save**.
3. Na ongeveer 1 minuut staat de app op de link hierboven.

## Gebruikerstesten

| Datum | Wat | Met wie |
|---|---|---|
| 26/10 | papieren prototype | medestudenten |
| 9/11 | klikbare app (demo-modus) | 3–5 kinderen van 8–12 |
| 30/11 | app + echte Bittle | kinderen + ouders |

We meten: tijd tot de eerste klik, het aantal hulpvragen, een smileyscore van 1 tot 5, en of het kind het nog eens wil doen.

## Logboek

| Datum | Wat |
|---|---|
| 12/10 | eerste bedieningspaneel + 10 macro's |
| 19/10 | 3 UX-concepten afgestemd op HW/SW |
| 22/10 | UX-slides finaal concept, doelgroep 8–12 |
| 26/10 | Figma-ontwerp + klikbaar prototype |
| 02/11 | Figma opgesplitst in 2 flows (opruimen / klaarleggen) |
| 03/11 | webapp v1 met demo-modus, Bluetooth/USB en test-commando's |
