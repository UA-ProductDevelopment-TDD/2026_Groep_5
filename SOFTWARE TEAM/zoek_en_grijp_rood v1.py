"""
ZOEK EN GRIJP (ROOD)  -  alles in 1 bestand, om te runnen in IDLE (F5).

De webcam van je laptop is (voorlopig) het "oog" van de Bittle:
houd een rood blokje voor de webcam en de Bittle reageert.

  ZOEKEN   geen rood te zien      -> Bittle wandelt rond (vooruit, draaien, vooruit, ...)
  RICHTEN  rood links / rechts    -> Bittle draait die kant op tot het recht voor hem ligt
  NADEREN  rood in het midden     -> Bittle wandelt vooruit tot het blokje groot (dichtbij) is
  GRIJPEN  rood groot en midden   -> stoppen, grijpen, arm 180 graden naar achter,
                                     loslaten in het bakje, arm terug -> weer zoeken

HOE:
  1. Eenmalig in cmd:  py -m pip install opencv-python numpy pyserial
  2. Sluit de Petoi Desktop App en Bittle Studio (anders is de COM-poort bezet).
  3. Open dit bestand in IDLE en druk F5.
  Toetsen in het camerabeeld:  q = stoppen   p = pauze (Bittle stil)   g = nu grijpen

DRAADLOOS (standaard): koppel de Bittle eenmalig in Windows
  Instellingen > Bluetooth en apparaten > Apparaat toevoegen > Bluetooth > BittleC9_SSP.
  Het script zoekt dan zelf de juiste Bluetooth-poort. Met kabel: zet VERBINDING = "usb".

LET OP: de Bittle wandelt echt! Zet hem op de vloer of houd hem in de gaten.
"""

# ======================= INSTELLINGEN =======================
VERBINDING = "bluetooth" # "bluetooth" = draadloos (BittleC9_SSP), "usb" = met kabel
PORT = None             # bv. "COM7" om zelf de poort te kiezen. None = automatisch zoeken
BITTLE_NAAM = "BittleC9" # Bluetooth-naam van JULLIE Bittle (zonder _SSP); zo vindt hij de juiste poort
MET_ROBOT = True        # False = alleen de webcam testen (commando's worden enkel getoond)
CAMERA = 0              # 0 = ingebouwde webcam, 1 = andere camera

KLEUR = "rood"
# HSV-grenzen voor rood (tint 0-179, verzadiging 0-255, helderheid 0-255). Rood zit rond 0 en 179.
# Afgesteld op jullie foto's in "Kleuren foto's/Rood": het blokje is daar vrij donker
# (tint 4-13, verzadiging ~100, helderheid ~70). Alle 7 geteste rode foto's: gezien,
# 5 blauwe foto's: geen vals rood. Te veel rood (bv. houten tafel)? Zet de 12 lager of de 90 hoger.
ROOD = [((0, 90, 45), (12, 255, 255)), ((165, 90, 45), (179, 255, 255))]
MIN_DEEL = 0.002        # rode vlekjes kleiner dan 0,2% van het beeld negeren (ruis)
MIDDEN_MARGE = 0.15     # blokje is "midden" binnen +-15% van het beeldmidden
DICHTBIJ = 0.06         # blokje is "dichtbij" (grijpen) als het 6% van het beeld vult

# Hoeveel beelden na elkaar iets moet kloppen (tegen flikkeren)
ZIEN_BEELDEN = 3        # zo vaak rood zien voor hij stopt met zoeken
KWIJT_BEELDEN = 15      # zo vaak niets zien voor hij weer gaat zoeken
GRIJP_BEELDEN = 8       # zo vaak "dichtbij en midden" voor hij grijpt

# Rondwandelen tijdens het zoeken: (commando, seconden), steeds opnieuw
ZOEKPLAN = [("kwkF", 3.0), ("kwkL", 1.5), ("kwkF", 3.0), ("kwkR", 2.0)]

# Grijparm (zelfde als bittle_grijp_drop.py; neem jullie afgestelde waarden over!)
CLAW_OPEN = 40          # klauw open    (joint 2)
CLAW_CLOSED = 0         # klauw dicht   (joint 2)
REACH_DOWN = -40        # arm naar beneden om te grijpen (joint 1)
CARRY = 45              # arm half omhoog met blokje     (joint 1)
HOME = 0                # normale positie van de arm     (joint 1)
BACK_ANGLE = 180        # arm naar achter, boven het bakje (joint 1)
LEG_BLOKJE_ZELF = True  # True = aftellen zodat je het blokje onder de klauw kan leggen
PLACE_SECONDS = 5       # seconden om het blokje te leggen
NA_GRIJPEN = "zoeken"   # "zoeken" = daarna verder zoeken, "stoppen" = script stopt

CALIB_SECONDS = 2       # eerst even in calibratiepositie
VERBOSE = False         # True = toon al het seriele verkeer
# ============================================================

import os
import sys
import time

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("OpenCV ontbreekt. Typ in cmd:  py -m pip install opencv-python numpy")

PAN, LIFT, CLAW = 0, 1, 2          # nek (draaien), arm (heffen), klauw
LEGS = [8, 9, 10, 11, 12, 13, 14, 15]
BAUD = 115200
STEP_DEG, STEP_DELAY = 3, 0.03


# ----------------------------------------------------------------------------
# Verbinding met de Bittle
# ----------------------------------------------------------------------------
class Bittle:
    def __init__(self, port):
        self.angles = {}
        self.laatste = None
        self.ser = None
        if port is None:                       # MET_ROBOT = False
            print("[ZONDER ROBOT] commando's worden alleen getoond.")
            return
        import serial
        print(f"Verbinden met {port} ...")
        try:
            self.ser = serial.Serial(port, BAUD, timeout=0.05, write_timeout=1)
        except serial.SerialException as e:
            sys.exit(f"Kan {port} niet openen ({e}).\n"
                     "  - Staat de Petoi Desktop App, Bittle Studio of de Petoi-app op je gsm nog verbonden? Sluit die.\n"
                     "  - Bluetooth: staat de Bittle aan? Koos je de UITGAANDE poort? Zet hem eens uit en aan.")
        self._wacht_opstart()
        self.lees_hoeken()

    def _wacht_opstart(self, max_s=8.0):
        t0 = last = time.time()
        while time.time() - t0 < max_s:
            raw = self.ser.readline()
            if raw:
                last = time.time()
                if b"Ready" in raw:
                    break
            elif time.time() - last > 1.5:
                break
        print("Verbonden.")

    def send(self, cmd, timeout=1.0, wacht=True):
        if VERBOSE or self.ser is None:
            print("  >", cmd)
        if self.ser is None:
            return []
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\n").encode())
        if not wacht:
            return []
        lines, t0 = [], time.time()
        while time.time() - t0 < timeout:
            raw = self.ser.readline()
            if not raw:
                continue
            txt = raw.decode(errors="ignore").strip()
            if txt:
                lines.append(txt)
                if VERBOSE:
                    print("  <", txt)
                if txt == cmd[0]:
                    break
        return lines

    def gang(self, cmd):
        """Loopcommando (kwkF, kwkL, kup, ...) alleen sturen als het verandert. Wacht niet."""
        if cmd == self.laatste:
            return
        self.laatste = cmd
        print(f"  -> Bittle: {cmd}")
        self.send(cmd, wacht=False)

    def lees_hoeken(self):
        if self.ser is None:
            return self.angles
        rows = []
        for line in self.send("j"):
            try:
                vals = [int(float(p)) for p in line.replace(",", " ").split()]
            except ValueError:
                continue
            if len(vals) >= 3:
                rows.append(vals)
        if rows:
            if len(rows) >= 2 and len(rows[-2]) == len(rows[-1]) and rows[-2][:3] == [0, 1, 2]:
                self.angles.update(dict(zip(rows[-2], rows[-1])))
            else:
                self.angles.update(dict(enumerate(rows[-1])))
        return self.angles

    def move(self, targets, speed=1.0):
        """Vloeiend naar {joint: hoek}. De nek (joint 0) wordt hier nooit gestuurd."""
        targets = {j: a for j, a in targets.items() if j != PAN}
        if LIFT in targets:
            targets[LIFT] = max(-90, min(180, targets[LIFT]))
        start = {j: self.angles.get(j, 0) for j in targets}
        grootste = max(abs(targets[j] - start[j]) for j in targets)
        stappen = max(1, int(grootste / STEP_DEG))
        for s in range(1, stappen + 1):
            f = s / stappen
            frame = {j: round(start[j] + (targets[j] - start[j]) * f) for j in targets}
            self.send("i" + " ".join(f"{j} {a}" for j, a in frame.items()), timeout=0.5)
            self.angles.update(frame)
            time.sleep(STEP_DELAY / speed)

    def skill(self, name):
        self.laatste = name
        self.send(name, timeout=8.0)
        time.sleep(0.3)
        self.lees_hoeken()

    def sluit(self):
        if self.ser:
            try:
                self.send("kup", timeout=2.0)
            except Exception:
                pass
            self.ser.close()


def is_bluetooth(p):
    tekst = f"{p.description} {p.hwid}".lower()
    return "bluetooth" in tekst or "bthenum" in tekst


def bt_adres(p):
    """Bluetooth-adres (12 hex-tekens) uit de hwid van een poort, of '' (inkomende poort)."""
    laatste = (p.hwid or "").upper().replace("\\", "&").split("&")[-1]
    adres = laatste.split("_")[0]
    return adres.lower() if len(adres) == 12 and set(adres) != {"0"} else ""


def bt_naam(adres):
    """Naam van een gekoppeld Bluetooth-apparaat (uit het Windows-register), of ''."""
    if not adres or os.name != "nt":
        return ""
    try:
        import winreg
        sleutel = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices" + "\\" + adres)
        waarde, _ = winreg.QueryValueEx(sleutel, "Name")
        return bytes(waarde).split(b"\x00")[0].decode(errors="ignore")
    except OSError:
        return ""


def bluetooth_uitgaand(poorten):
    """Een gekoppelde Bittle..._SSP krijgt in Windows TWEE COM-poorten: inkomend en uitgaand.
    Alleen de uitgaande werkt. Daarin staat het adres van de robot, bij de inkomende 000000000000.
    (Zelfde methode als echte_bittle.py.)"""
    uit = []
    for p in poorten:
        if not is_bluetooth(p):
            continue
        laatste = (p.hwid or "").upper().replace("\\", "&").split("&")[-1]
        adres = laatste.split("_")[0]
        if adres and set(adres) != {"0"}:
            uit.append(p)
    return uit


try:
    _MAP = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _MAP = os.getcwd()
ONTHOUD = os.path.join(_MAP, "bittle_poort.txt")


def kies_poort():
    from serial.tools import list_ports
    poorten = list(list_ports.comports())
    namen = [p.device for p in poorten]

    # 0) Bluetooth: de poort van BITTLE_NAAM opzoeken (gaat voor alles)
    if VERBINDING == "bluetooth":
        op_naam = [p for p in bluetooth_uitgaand(poorten)
                   if BITTLE_NAAM.lower() in bt_naam(bt_adres(p)).lower()]
        if len(op_naam) == 1:
            p = op_naam[0]
            print(f"Bittle gevonden: {bt_naam(bt_adres(p))} op {p.device}")
            return p.device

    # 1) eerder gekozen poort onthouden?
    if os.path.exists(ONTHOUD):
        vorige = open(ONTHOUD, encoding="utf-8").read().strip()
        if vorige in namen:
            print(f"Bittle-poort van vorige keer: {vorige}  (andere kiezen? verwijder bittle_poort.txt)")
            return vorige

    # 2) automatisch zoeken
    if VERBINDING == "bluetooth":
        uit = bluetooth_uitgaand(poorten)
        if len(uit) == 1:
            print(f"Bluetooth-poort van de Bittle gevonden: {uit[0].device}")
            return uit[0].device
        if len(uit) > 1:
            print(f"Ik vond geen poort met de naam '{BITTLE_NAAM}'. Klopt BITTLE_NAAM bovenaan?\n"
                  "Er zijn meerdere Bluetooth-poorten (" + ", ".join(p.device for p in uit) + ").\n"
                  "Windows zegt niet welke van de Bittle is: kies hieronder EEN KEER, ik onthoud het.\n"
                  "Tip: in Instellingen > Bluetooth > Meer Bluetooth-instellingen > tabblad COM-poorten\n"
                  "     staat bij welke poort 'BittleC9_SSP' en 'Uitgaand' hoort.")
        else:
            print("Geen gekoppelde Bittle via Bluetooth gevonden.\n"
                  "  1. Zet de Bittle aan (batterij).\n"
                  "  2. Windows: Instellingen > Bluetooth en apparaten > Apparaat toevoegen > Bluetooth\n"
                  "     > kies BittleC9_SSP (pincode gevraagd? probeer 0000 of 1234).\n"
                  "  3. Start dit script opnieuw. Of kies hieronder zelf een poort.")
    else:
        usb = [p for p in poorten if not is_bluetooth(p)]
        if len(usb) == 1:
            print(f"USB-poort van de Bittle gevonden: {usb[0].device}")
            return usb[0].device

    # 3) zelf kiezen (en onthouden)
    if not poorten:
        sys.exit("Geen COM-poorten gevonden. Is de Bittle gekoppeld (Bluetooth) of aangesloten (USB)?")
    print("Beschikbare poorten:")
    for i, p in enumerate(poorten, 1):
        if is_bluetooth(p):
            naam = bt_naam(bt_adres(p))
            soort = f"Bluetooth: {naam}" if naam else ("Bluetooth (inkomend, niet kiezen)" if not bt_adres(p) else "Bluetooth")
        else:
            soort = "USB/ander"
        print(f"  {i}. {p.device:8s} [{soort}]")
    while True:
        k = input("Kies het nummer van de Bittle-poort: ").strip()
        if k.isdigit() and 1 <= int(k) <= len(poorten):
            keuze = poorten[int(k) - 1].device
            try:
                with open(ONTHOUD, "w", encoding="utf-8") as f:
                    f.write(keuze)
                print(f"Onthouden: {keuze} (volgende keer vraag ik het niet meer)")
            except OSError:
                pass
            return keuze


# ----------------------------------------------------------------------------
# Kleurherkenning (zelfde methode als lego_kleur.py)
# ----------------------------------------------------------------------------
def zoek_rood(beeld):
    """Grootste rode vlek: dict met kader, midden, oppervlak. Of None."""
    hsv = cv2.cvtColor(cv2.GaussianBlur(beeld, (5, 5), 0), cv2.COLOR_BGR2HSV)
    masker = None
    for laag, hoog in ROOD:
        m = cv2.inRange(hsv, np.array(laag), np.array(hoog))
        masker = m if masker is None else cv2.bitwise_or(masker, m)
    kern = np.ones((3, 3), np.uint8)
    masker = cv2.morphologyEx(masker, cv2.MORPH_OPEN, kern)
    masker = cv2.morphologyEx(masker, cv2.MORPH_CLOSE, kern)
    contouren, _ = cv2.findContours(masker, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    beste = None
    min_opp = MIN_DEEL * beeld.shape[0] * beeld.shape[1]
    for c in contouren:
        opp = cv2.contourArea(c)
        if opp >= min_opp and (beste is None or opp > beste["oppervlak"]):
            x, y, b, h = cv2.boundingRect(c)
            beste = {"kader": (x, y, b, h), "midden": (x + b // 2, y + h // 2), "oppervlak": opp}
    return beste


def beoordeel(blok, breedte, hoogte):
    """Wat moet de Bittle doen met wat de camera ziet?"""
    if blok is None:
        return "ZOEKEN"
    afwijking = (blok["midden"][0] - breedte / 2) / breedte     # -0.5 links ... +0.5 rechts
    if afwijking < -MIDDEN_MARGE:
        return "LINKS"
    if afwijking > MIDDEN_MARGE:
        return "RECHTS"
    if blok["oppervlak"] / (breedte * hoogte) < DICHTBIJ:
        return "NADEREN"
    return "GRIJPEN"


def teken(beeld, blok, toestand, tekst):
    h, b = beeld.shape[:2]
    x1, x2 = int(b * (0.5 - MIDDEN_MARGE)), int(b * (0.5 + MIDDEN_MARGE))
    cv2.line(beeld, (x1, 0), (x1, h), (200, 200, 200), 1)
    cv2.line(beeld, (x2, 0), (x2, h), (200, 200, 200), 1)
    if blok:
        x, y, bb, hh = blok["kader"]
        cv2.rectangle(beeld, (x, y), (x + bb, y + hh), (0, 0, 255), 3)
        deel = 100 * blok["oppervlak"] / (b * h)
        cv2.putText(beeld, f"rood {deel:.1f}% (grijpen vanaf {DICHTBIJ*100:.0f}%)",
                    (x, max(18, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    cv2.rectangle(beeld, (0, h - 32), (b, h), (0, 0, 0), -1)
    cv2.putText(beeld, f"{toestand}: {tekst}", (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(beeld, "q=stop  p=pauze  g=grijpen", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


# ----------------------------------------------------------------------------
# Grijpen en droppen
# ----------------------------------------------------------------------------
def grijp_en_drop(b, toon):
    print("\n=== GRIJPEN ===")
    b.gang("kup")                               # stoppen met wandelen
    time.sleep(1.0)
    b.lees_hoeken()
    toon("klauw open, arm naar beneden")
    b.move({CLAW: CLAW_OPEN})
    b.move({LIFT: REACH_DOWN}, speed=0.7)
    if LEG_BLOKJE_ZELF:
        for t in range(PLACE_SECONDS, 0, -1):
            toon(f"leg het blokje onder de klauw ... {t}")
            time.sleep(1)
    toon("klauw dicht")
    b.move({CLAW: CLAW_CLOSED}, speed=0.6)
    time.sleep(0.4)
    toon(f"arm naar achter ({BACK_ANGLE})")
    b.move({LIFT: CARRY}, speed=0.6)
    b.move({LIFT: BACK_ANGLE}, speed=0.4)
    toon("loslaten in het bakje")
    b.move({CLAW: CLAW_OPEN})
    time.sleep(0.8)
    toon("arm terug")
    b.move({LIFT: CARRY}, speed=0.8)
    b.move({CLAW: CLAW_CLOSED})
    b.move({LIFT: HOME}, speed=0.8)
    print("=== KLAAR MET GRIJPEN ===\n")


# ----------------------------------------------------------------------------
# Hoofdprogramma
# ----------------------------------------------------------------------------
def main():
    cam = cv2.VideoCapture(CAMERA)
    if not cam.isOpened():
        sys.exit(f"Webcam {CAMERA} niet gevonden. Probeer CAMERA = 1 bovenaan.")

    if MET_ROBOT:
        try:
            import serial  # noqa: F401
        except ImportError:
            sys.exit("pyserial ontbreekt. Typ in cmd:  py -m pip install pyserial")
        b = Bittle(PORT or kies_poort())
    else:
        b = Bittle(None)

    venster = "Bittle zoekt ROOD"
    laatste_beeld = [None]

    def toon(tekst):
        """Tekst op het (stilstaande) camerabeeld tijdens het grijpen."""
        print("   ", tekst)
        if laatste_beeld[0] is not None:
            beeld = laatste_beeld[0].copy()
            teken(beeld, None, "GRIJPEN", tekst)
            cv2.imshow(venster, beeld)
            cv2.waitKey(1)

    try:
        print("\nCalibratiepositie (alle joints op 0) ...")
        if b.ser:
            b.move({j: 0 for j in [LIFT, CLAW] + LEGS}, speed=0.5)
            time.sleep(CALIB_SECONDS)
        print("Rechtstaan ...")
        b.skill("kup")
        b.move({LIFT: HOME, CLAW: CLAW_CLOSED})

        zien = kwijt = dichtbij = 0
        modus = "ZOEKEN"            # ZOEKEN of VOLGEN
        net_gegrepen = False        # na grijpen: eerst moet het rood uit beeld zijn
        plan_i, plan_t = 0, time.time()
        pauze = False
        print("\nKlaar. Houd een rood blokje voor de webcam. (q = stoppen)")

        while True:
            ok, beeld = cam.read()
            if not ok:
                print("Geen beeld van de webcam.")
                break
            hoogte, breedte = beeld.shape[:2]
            blok = zoek_rood(beeld)
            oordeel = beoordeel(blok, breedte, hoogte)

            # tellers tegen flikkeren
            if blok:
                zien, kwijt = zien + 1, 0
            else:
                zien, kwijt = 0, kwijt + 1
            dichtbij = dichtbij + 1 if oordeel == "GRIJPEN" and not net_gegrepen else 0
            if net_gegrepen and kwijt >= KWIJT_BEELDEN:
                net_gegrepen = False

            if modus == "ZOEKEN" and zien >= ZIEN_BEELDEN:
                modus = "VOLGEN"
                print("Rood gezien!")
            elif modus == "VOLGEN" and kwijt >= KWIJT_BEELDEN:
                modus = "ZOEKEN"
                plan_t = time.time()
                print("Rood kwijt, weer zoeken.")

            toets = cv2.waitKey(1) & 0xFF
            if toets == ord("q"):
                break
            if toets == ord("p"):
                pauze = not pauze
                b.gang("kup")
                print("PAUZE" if pauze else "verder")
            if toets == ord("g"):
                dichtbij = GRIJP_BEELDEN

            # wat doet de Bittle?
            if pauze:
                tekst = "pauze (p = verder)"
            elif net_gegrepen and blok:
                b.gang("kup"); tekst = "net gegrepen: haal het blokje uit beeld"
            elif modus == "ZOEKEN" or net_gegrepen:
                cmd, duur = ZOEKPLAN[plan_i]
                if time.time() - plan_t > duur:
                    plan_i, plan_t = (plan_i + 1) % len(ZOEKPLAN), time.time()
                    cmd = ZOEKPLAN[plan_i][0]
                b.gang(cmd)
                tekst = f"rondwandelen ({cmd})"
            elif dichtbij >= GRIJP_BEELDEN:
                laatste_beeld[0] = beeld.copy()
                grijp_en_drop(b, toon)
                zien = kwijt = dichtbij = 0
                net_gegrepen = True
                print("Haal het blokje uit beeld; daarna zoekt hij verder.")
                if NA_GRIJPEN == "stoppen":
                    break
                modus, plan_t = "ZOEKEN", time.time()
                continue
            elif oordeel == "LINKS":
                b.gang("kwkL"); tekst = "blokje links -> draaien (kwkL)"
            elif oordeel == "RECHTS":
                b.gang("kwkR"); tekst = "blokje rechts -> draaien (kwkR)"
            elif oordeel == "NADEREN":
                b.gang("kwkF"); tekst = "recht vooruit -> naderen (kwkF)"
            elif oordeel == "GRIJPEN":
                b.gang("kup"); tekst = f"dichtbij -> stilstaan ({dichtbij}/{GRIJP_BEELDEN})"
            else:                                  # even niets gezien tijdens volgen
                b.gang("kup"); tekst = "even kwijt -> stilstaan"

            teken(beeld, blok, modus, tekst)
            cv2.imshow(venster, beeld)
    except KeyboardInterrupt:
        print("\nGestopt (Ctrl+C).")
    finally:
        print("Afsluiten: Bittle staat recht.")
        b.sluit()
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
