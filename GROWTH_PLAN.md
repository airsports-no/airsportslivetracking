# AirSports Growth Plan — Raw Notes

Captured 2026-04-25. **Working document** — these are exploration notes,
not a committed strategy. Polish before any outreach.

---

## Context

AirSports er ideell organisasjon avhengig av sponsorer. Plattformen
brukes for presisjonsflyvning og lignende konkurranseformater (norsk/europeisk
tradisjon, nesten ikke-eksisterende i USA).

Frank har nylig bygd flashy frontside, og planlegger å flytte
contest-dashboard til sub-domene (standard SaaS-pattern).

---

## Spor 1 — Garmin som hovedsponsor

### Hook

Garmin sponser allerede EAA, AirVenture, GA-influensere. Aviation er
kjernemarked. Pilot-skill-development er deres språk.

### Posisjoneringsproblem (må adresseres)

Konkurransekonseptet er **eksplisitt uten GPS**. Garmin = GPS. Ironi
må håndteres, ikke gjemmes.

### Vinkler som kan funke

1. **Skill-complement:** Pilotene trener stick-and-rudder + navigasjon i
   konkurranse, og er bedre brukere av Garmin-avionics i daglig flyvning.
2. **Safety-integrasjon:** Pilotene konkurrerer uten GPS, men plattformen
   tracker dem trygt via Garmin inReach / aktivitetsklokker. Dette er en
   konkret integrasjon å bygge — ikke bare retorikk.
3. **Trening for instrumentbruk:** Mange piloter overdriver avhengigheten
   av glass cockpit. Konkurransen tvinger fram backup-skill, som er
   sikkerhetsargumentet for hvorfor *også* Garmin-piloter trenger det.

### Realistisk forventning

Sannsynlig: Ingen respons eller standard-avslag. Asymmetrisk upside —
e-post koster null, sponsor potensielt sigificant.

### Pre-rekvisitter før e-post sendes

- Marketing-side ferdig og polert
- Onboarding sømløs nok at en Garmin-markedssjef kan teste
  plattformen på 5 minutter
- Sub-domene-split fullført (app.airsports.no e.l.)
- Konkret integrasjon-pitch (ikke bare «hva med å sponse oss?»)

---

## Spor 2 — US-influensere / aviation YouTubers

### Markedsproblem

Presisjonsflyving har nesten ingen fotfeste i USA. Trenger reframing
fra «World Precision Flying Championship qualifier» til «test your
stick-and-rudder skills against tight tolerance scoring.»

### Influenser-shortlist (verifisert relevans før outreach)

| Navn | Match | Hvorfor |
|------|-------|---------|
| Steve Thorne (FlightChops) | **Sterk** | Skill-fokus, har gjort collabs, riktig audience |
| Aviation101 | Sterk | Yngre, app-vennlig demografi |
| Mike Patey | Medium | Builder-fokus, men ekstrem audience-engagement |
| Steveo Kinevo | Medium | Rekkevidde, men mer entertainment enn skill |
| ~~Trent Palmer~~ | **Avvist** | STOL/backcountry — feil sport |
| ~~Dan Gryder~~ | Avvist | Accident-analyse, feil tone |

### Hooken som faktisk får videoer

**Solo Challenge Mode.** Én pilot flyr samme rute som VM-deltakere,
får score, deler lenke. *«I flew the same route as the world champions
and got destroyed»* — det er den delbare videoen.

Uten denne moden har en YouTuber ingen video å lage alene. Med den,
blir det selvforklarende viralt.

### Outreach-rekkefølge

Ikke 5 stk samtidig — én av gangen, justere pitchen basert på respons.
Start med Steve Thorne (mest aligned).

---

## Spor 3 — Sub-domene-split + marketing-side

Trivielt teknisk arbeid. Marketing-side på `airsports.no` (statisk,
CDN-cachet gratis), app på `app.airsports.no` eller `compete.airsports.no`.

Gjør samtidig med CDN-shadow-arbeidet — den nye LB-en kan rute
sub-domener fra start.

---

## Spor 4 — Onboarding-sømløshet

**Vagest definert spor — trenger konkretisering.**

Spørsmål å besvare før Garmin/influenser-outreach:

- Kan en pilot prøve plattformen uten å lage konto?
- Finnes det en demo-konkurranse med ferdig data å utforske?
- Hvor mange klikk fra forside → første flight-replay?
- Solo Challenge Mode (se Spor 2) — hvor mye arbeid?

---

## Sekvenseringsregel

Garmin og influensere treffer begge på onboarding-flaskehalsen. Hvis
en nysgjerrig person ikke kommer i gang på 60 sekunder, mister du dem.

**Outreach skjer ikke før onboarding er polert.**

Anbefalt rekkefølge:
1. Marketing-side + sub-domene-split (i gang)
2. CDN-shadow + cutover (i kveld + senere)
3. Solo Challenge Mode (ny feature)
4. Onboarding-polish (trial-konkurranse uten konto?)
5. *Så* Garmin-e-post + Steve Thorne-kontakt

---

## Energi/timing-advarsel

Strategi-planlegging når man er sliten gir systematisk
for-optimistiske vurderinger og dårlig follow-through. Disse notatene
er bevisst rå. Polish dem til outreach-tekst på en dag med høy body
battery.
