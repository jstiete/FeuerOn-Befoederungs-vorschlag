
""" Skript zur Prüfung der Beförderungsvorschläge gem. Niedersächsischer Feuerwehrverordnung
    anhand eines Datenexports als csv-Datei aus FeuerON.

    Copyright: © 2025 jstiete
    License: MIT
"""

from datetime import datetime
from datetime import timedelta
import sys
import pandas as pd
from pathlib import Path
import argparse
import logging
import re
import enum

# Logger für Konsole erstellen:
logger = logging.getLogger(__name__)
logFormatter = logging.Formatter('%(asctime)s\t- %(levelname)s\t- %(filename)s:(%(lineno)d) - %(message)s')
ch = logging.StreamHandler(stream=sys.stdout)
ch.setFormatter(logFormatter)
if not logger.handlers:
    logger.addHandler(ch)

# globale Variable
global now
now = datetime.now() # Just for Debugging :) Wird später überschrieben.


class meta():
    """ Abstracte Klasse für Zeitabschnitte"""
    def __init__(self, name:str, von:datetime.date, bis:(datetime.date, None)):
        self.name = name
        self.von = von
        self.bis = bis

class Lehrgang(meta):
    """" Definiert einen Lehrgang / Fortbildung"""
    def __init__(self, name:str, von:datetime.date, bis:(datetime.date, None), bestanden):
        meta.__init__(self, name, von, bis)
        self.bestanden = bestanden
    class status(enum.StrEnum):
        BESTANDEN = "Bestanden"
        NICHTBESTANDEN = "Nicht Bestanden"

class LehrgangEnum(enum.StrEnum):
    """ Übersicht der erfassten Lehrgänge / Fortbildungen"""
    TM1 = "Truppmannausbildung Teil 1"
    TM2 = "Truppmannausbildung Teil 2"
    GA = "Grundausbildung (alte Form)"
    QS1 = "Qualifikationsstufe Einsatzfähigkeit"
    QS2 = "Qualifikationsstufe Truppmitglied"
    QS3 = "Qualifikationsstufe Truppführende/Truppführender"
    TF = "Truppführer"
    GF1 = "Gruppenführer Teil 1"
    GF2 = "Gruppenführer Teil 2"
    ZF1 = "Zugführer Teil 1"
    ZF2 = "Zugführer Teil 2"
    LFW = "Leiter einer Feuerwehr"
    AGT = "Atemschutzgeräteträgerlehrgang"
    FUNKER = "Sprechfunkerlehrgang"
    MASCH = "Maschinistenlehrgang"
    TH = "Technische Hilfeleistung"

class Amt(meta):
    """" Definiert ein Amt / Dienststellung"""
    def __init__(self, name:str, von:datetime.date, bis:(datetime.date, None)):
        meta.__init__(self, name, von, bis)

class Dienstgrad(meta):
    """" Definiert einen Dienstgrad"""
    def __init__(self, name:str, von:datetime.date, bis:(datetime.date, None)):
        meta.__init__(self, name, von, bis)

    # Reihenfolge der Dienstgrade mit den entsp Abkürzungen für männlich, weiblich
    # nach neuer Verordnung
    Reihenfolge_W_neu =  ("FFA", "FF", "OFF", "HFF", "EHFF",  "BM", "OBM", "HBM", "EHBM",  "BrI", "OBrI", "HBrI", "EHBrI", "GemBrI")
    Reihenfolge_M_neu =  ("FMA", "FM", "OFM", "HFM", "EHFM",  "BM", "OBM", "HBM", "EHBM",  "BrI", "OBrI", "HBrI", "EHBrI", "GemBrI")
    # nach der alten Verordnung
    Reihenfolge_W_alt = ("FFA", "FF", "OFF", "HFF", "1.HFF", "LM", "OLM", "HLM", "1.HLM", "BM",  "OBM",  "HBM",  "1.HBM")
    Reihenfolge_M_alt = ("FMA", "FM", "OFM", "HFM", "1.HFM", "LM", "OLM", "HLM", "1.HLM", "BM",  "OBM",  "HBM",  "1.HBM")
    Reihenfolge_M = Reihenfolge_M_neu
    Reihenfolge_W = Reihenfolge_W_neu

class Abteilung(meta):
    """Definiert eine Abteilungszugehörigkeit"""
    def __init__(self, name:str, von:datetime.date, bis:(datetime.date, None)):
        meta.__init__(self, name, von, bis)

class AbteilungEnum(enum.StrEnum):
    """Auflistung möglicher Abteilungen"""
    KF = "Kinderfeuerwehr"
    JF = "Jugendfeuerwehr"
    FF = "Einsatzabteilung FF"
    AA = "Altersabteilung, Ehrenabteilung"
    PASSIV = "Fördernde Mitglieder"

class Person():
    """Person samt Daten, deren Voraussetungen überprüft werden sollen."""
    def __init__(self, Vorname:str, Nachname:str, Geburtsdatum:datetime.date, Geschlecht, PersonalNr:str, Einstellungsdatum:(datetime.date,float)=float('Nan')):
        self.Vorname = Vorname
        self.Nachname = Nachname
        self.Geburtsdatum = Geburtsdatum
        self.Geschlecht = Geschlecht
        self.Einstellungsdatum = Einstellungsdatum
        self.PersonalNr = PersonalNr
        self.Abteilungen = []
        self.Dienstgrade = []
        self.Amter = []
        self.Lehrgange = []


def AnzTage(input:(Lehrgang, Amt, Dienstgrad, Abteilung)):
    global now
    if input.bis is None:
        ende = now
    else:
        ende = input.bis
    return (ende-input.von).days

def AnzTage2(inputlist:list):
    """Berechnet die Anzahl der Tage ohne zeitliche Überschneidungen für eine von meta abgeleitete Liste.
       Zum Beispiel die Dauer aller Elemente in der Liste Abteilungen."""
    global now
    #Sortiere nach Beginn
    sortedlist = sorted(inputlist, key=lambda x: x.von)
    # falls die früheste Mitgliedschaft durchgängig bis jetzt ist:
    if sortedlist[0].bis == now:
        dauer = (sortedlist[0].bis - sortedlist[0].von).days
    else:
        dauer=0
        # Alle Mitgliedschaften aufaddieren und doppelte Zeiträume berücksichtigen
        for idx, element in enumerate(sortedlist):
            if idx>0 and element.von <= sortedlist[idx-1].bis:
                # Die Mitgliedschaft startet, bevor die vorherige endet. -> Beginn verschieben.
                element.von = sortedlist[idx-1].bis + timedelta(days=1)
            dauer += (element.bis - element.von).days
    logger.debug(f"    Gesamtdauer ohne Überschneidungen (in {', '.join(e.name for e in sortedlist)}): {dauer} Tage.")
    return dauer

def AnzJahre(input:list):
    return AnzTage2(input)/365

def AnzDienstJahreAbt(Abteilungen:list, abteilung:AbteilungEnum):
    """ Filter die Anzahl der Dienstjahre für eine besimmte Abteilung aus den hinterlegten Abteilungen
    und berechnet die Dauer der Dienstzeit ohne Überlappung."""
    listAbt = list(filter(lambda x: x.name == abteilung.value, Abteilungen))
    if len(listAbt) == 0:
        return 0
    return AnzTage2(listAbt)/365

def AnzDienstJahreFF(Abteilungen:list):
    """ Filter die Anzahl der Dienstjahre Abteilung 'Einsatzabteilung FF' aus den hinterlegten Abteilungen
    und berechnet die Dauer der Dienstzeit ohne Überlappung."""
    return AnzDienstJahreAbt(Abteilungen, AbteilungEnum.FF)

def AnzDienstJahreJF(Abteilungen:list):
    """ Filter die Anzahl der Dienstjahre Abteilung 'Jugendfeuerwehr' aus den hinterlegten Abteilungen
    und berechnet die Dauer der Dienstzeit ohne Überlappung."""
    return AnzDienstJahreAbt(Abteilungen, AbteilungEnum.JF)

def AnzDienstJahreFFnachLehrgang(person:Person, lehrgang:LehrgangEnum):
    """ Filter die Anzahl der Dienstjahre Abteilung 'Einsatzabteilung FF' aus den hinterlegten Abteilungen
        und berechnet die Dauer der Dienstzeit nach dem Ende des Lehrgangs ohne Überlappung.
        'Mindestdienstzeit nach Abschluss der xxx Ausbildung"""
    global now
    # Filtere Abteilungen nach 'Einsatzabteilung FF' und sortiere nach Beginn
    listAbt = filter(lambda x: x.name == AbteilungEnum.FF.value, person.Abteilungen)
    listAbt = sorted(listAbt, key=lambda x: x.von)

    #Suche Lehrgangsende
    listLehrgange = filter(lambda x: (x.name == lehrgang.value and x.bestanden == Lehrgang.status.BESTANDEN), person.Lehrgange)
    listLehrgange = sorted(listLehrgange, key=lambda x: x.bis)

    if len(listAbt) == 0 or len(listLehrgange) == 0:
        # der Lehrgang ist nicht erfolgreich abgeschlossen
        return 0

    start = listLehrgange[-1].bis

    # falls die früheste Mitgliedschaft durchgängig bis jetzt ist:
    if listAbt[0].bis == now:
        # und der Lehrgang schon davor beendet war ???
        if start > listAbt[0].von:
            dauer = (listAbt[0].bis - start).days
        else:
            dauer = (listAbt[0].bis - listAbt[0].von).days
    else:
        dauer=0
        # Alle Mitgliedschaften aufaddieren und doppelte Zeiträume berücksichtigen
        for idx, element in enumerate(listAbt):
            if element.bis < start:
                #Mitgliedschaft war ohne Lehrgang beendet
                continue
            if idx>0 and element.von <= listAbt[idx-1].bis:
                # Die Mitgliedschaft startet, bevor die vorherige endet. -> Beginn verschieben.
                element.von = listAbt[idx-1].bis + timedelta(days=1)
            if element.von < start:
                dauer = (element.bis - start).days
            else:
                dauer += (element.bis - element.von).days
    logger.debug(f"    Anzahl Dienstjahre in Einsatzabteilng nach Datum {start.strftime('%d.%m.%Y')}: {dauer/365}")
    return dauer / 365


def HatFortb(inputlist, name:LehrgangEnum):
    """Prüft, ob in der inputlist ein Element vom Typ Lehrgang mit passendem Namen und dem Status Bestanden vorhanden ist."""
    for lehrgang in inputlist:
        if lehrgang.name == name.value and lehrgang.bestanden == 'Bestanden':
            logger.debug(f"    Lehrgang '{lehrgang.name}' hat Status '{lehrgang.bestanden}'")
            return True
    return False

def AnzTechLehrgange(lehrgange:list):
    """Prüft die Anzahl der hinterlegten technischen Lehrgänge."""
    techLehrgange = [LehrgangEnum.AGT, LehrgangEnum.FUNKER, LehrgangEnum.MASCH, LehrgangEnum.TH]
    listLehrgange = list(filter(lambda x: (x.name in techLehrgange and x.bestanden == Lehrgang.status.BESTANDEN),lehrgange))
    return len(listLehrgange)


def check_FM(person:Person):
    """Checks für Feuerwehrfrau-/mann (alt. FF/FM):
         - Mindestdienstzeit 1 Jahr
         - abgeschlossene MGA-QS1 ODER Truppmannausbildung Teil 1 ODER Grundausbildungslehrgang"""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.QS1) or
             HatFortb(person.Lehrgange, LehrgangEnum.TM1) or
             HatFortb(person.Lehrgange, LehrgangEnum.GA))
    cond2 = (AnzDienstJahreFF(person.Abteilungen) >= 1 or
             AnzDienstJahreJF(person.Abteilungen) >= 2)
    #logger.debug(f"  check_FM(): cond1: {cond1}, cond2: {cond2}")
    return cond1 and cond2

def check_OFM(person:Person):
    """Checks für Oberfeuerwehrfrau-/mann (alt. OFF/OFM):
         - Mindestdienstzeit 2 Jahre
         - abgeschlossene MGA-QS1 UND MGA-QS2 ODER Truppmannausbildung Teil 1 und 2 ODER Grundausbildungslehrgang"""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.QS2) or
             HatFortb(person.Lehrgange, LehrgangEnum.TM2) or
             HatFortb(person.Lehrgange, LehrgangEnum.GA))
    cond2 = AnzDienstJahreFF(person.Abteilungen) >= 2
    #logger.debug(f"  check_OFM(): cond1: {cond1}, cond2: {cond2}")
    return cond1 and cond2

def check_HFM(person:Person):
    """Checks für Hauptfeuerwehrfrau-/mann (alt. HFF/HFM):
         - Mindestdienstzeit 5 oder 10 Jahre
         - Mind 3 jährige Dienstzeit nach Abschluss TF bzw. QS3
           oder
         - Mind. 10 jährige Dienstzeit nach Abschluss TM2 und zusätzlich 2 techn. Lehrgänge """
    cond1 = AnzDienstJahreFF(person.Abteilungen) >= 5
    cond2 = (HatFortb(person.Lehrgange, LehrgangEnum.QS3) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.QS3) >= 3)
    cond3 = (HatFortb(person.Lehrgange, LehrgangEnum.TF) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.TF) >= 3)
    cond4 = (HatFortb(person.Lehrgange, LehrgangEnum.TM2) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.TM2) >= 3 and
             AnzTechLehrgange(person.Lehrgange)>=2)
    logger.debug(f"  check_HFM(): cond1: {cond1}, cond2: {cond2}, cond3: {cond3}, cond4: {cond4}")
    return cond1 and (cond2 or cond3 or cond4)

def check_EHFM(person:Person):
    """Checks für Erster Hauptfeuerwehrfrau-/mann (alt. EHFF/EHFM):
         - Mind 10 Jahre Dienstzeit nach abgeschl. QS3 oder TF
           oder
         - Mind. 20 Jahre Dienstzeit nach abgeschl. TM Teil 2 und zusätzlich 2 techn. Lehrgänge """
    cond1 = AnzDienstJahreFF(person.Abteilungen) >= 10
    cond2 = (HatFortb(person.Lehrgange, LehrgangEnum.QS3) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.QS3) >= 10)
    cond3 = (HatFortb(person.Lehrgange, LehrgangEnum.TF) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.TF) >= 10)
    cond4 = (HatFortb(person.Lehrgange, LehrgangEnum.TM2) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.TM2) >= 20 and
             AnzTechLehrgange(person.Lehrgange)>=2)
    logger.debug(f"  check_EHFM(): cond1: {cond1}, cond2: {cond2}, cond3: {cond3}, cond4: {cond4}")
    return cond1 and (cond2 or cond3 or cond4)

def check_BM(person:Person):
    """Checks für Brandmeister(in) (alt. LM):
         - Mindestdienstzeit 5 Jahre
         - Lehrgänge mind. GF1 und GF2 """
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.GF1) and
             HatFortb(person.Lehrgange, LehrgangEnum.GF2) and
             AnzDienstJahreFF(person.Abteilungen)>=5)
    logger.debug(f"  check_BM(): cond1: {cond1}")
    return cond1

def check_OBM(person:Person):
    """ Checks für Oberbrandmeister(in) (alt. OLM):
          - Lehrgänge mind. GF1 und GF2.
          - Mindestdienstzeit 6 Jahre nach Abschluss der vorgeschriebenen Ausbildung."""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.GF1) and
             HatFortb(person.Lehrgange, LehrgangEnum.GF2) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.GF2) >= 6)
    logger.debug(f"  check_OBM(): cond1: {cond1}")
    return cond1

def check_HBM(person:Person):
    """ Checks für Hauptbrandmeister(in) (alt. HLM):
          - Lehrgänge mind. GF1 und GF2.
          - Mindestdienstzeit 12 Jahre nach Abschluss der vorgeschriebenen Ausbildung."""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.GF1) and
             HatFortb(person.Lehrgange, LehrgangEnum.GF2) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.GF2) >= 12)
    logger.debug(f"  check_HBM(): cond1: {cond1}")
    return cond1

def check_EHBM(person:Person):
    """ Checks für Erste(r) Hauptbrandmeister(in) (alt. EHLM):
          - Lehrgänge mind. GF1 und GF2.
          - Mindestdienstzeit 18 Jahre nach Abschluss der vorgeschriebenen Ausbildung."""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.GF1) and
             HatFortb(person.Lehrgange, LehrgangEnum.GF2) and
             AnzDienstJahreFFnachLehrgang(person, LehrgangEnum.GF2) >= 18)
    logger.debug(f"  check_EHBM(): cond1: {cond1}")
    return cond1

def check_BrI(person:Person):
    """ Checks für Brandinspektor(in) (alt. BM):
          - Lehrgänge mind. GF1 und GF2.
          - mindest Dienstjahre 9
        TODO: Voraussetzungen in Stützpunkt/ Schwerpunktwehr und Bemerkungen beachten!"""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.GF1) and
             HatFortb(person.Lehrgange, LehrgangEnum.GF2) and
             AnzDienstJahreFF(person.Abteilungen) >= 9)
    logger.debug(f"  check_BrI(): cond1: {cond1}")
    return cond1

def check_OBrI(person:Person):
    """ Checks für Oberbrandinspektor(in) (alt. OBM):
          - Mind 10 Dienstjahre
          - Lehrgänge mind. ZF1 und ZF2.
        TODO: Leiter einer Feuerwehr?"""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.ZF1) and
             HatFortb(person.Lehrgange, LehrgangEnum.ZF2) and
             AnzDienstJahreFF(person.Abteilungen) >= 10)
    logger.debug(f"  check_OBrI(): cond1: {cond1}")
    return cond1

def check_HBrI(person:Person):
    """ Checks für Hauptbrandinspektor(in) (alt. HBM):
          - Mind 11 Dienstjahre
          - Lehrgänge mind. ZF1 und ZF2, Leiter einer Feuerwehr
        TODO: Verbandsführer?"""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.ZF1) and
             HatFortb(person.Lehrgange, LehrgangEnum.ZF2) and
             HatFortb(person.Lehrgange, LehrgangEnum.LFW) and
             AnzDienstJahreFF(person.Abteilungen) >= 11)
    logger.debug(f"  check_HBrI(): cond1: {cond1}")
    return cond1

def check_EHBrI(person:Person):
    """ Checks für Erste(r) Hauptbrandinspektor(in) (alt. EHBM):
          - Mind 12 Dienstjahre
          - Lehrgänge mind. ZF1 und ZF2, Leiter einer Feuerwehr
        TODO: Verbandsführer?"""
    cond1 = (HatFortb(person.Lehrgange, LehrgangEnum.ZF1) and
             HatFortb(person.Lehrgange, LehrgangEnum.ZF2) and
             HatFortb(person.Lehrgange, LehrgangEnum.LFW) and
             AnzDienstJahreFF(person.Abteilungen) >= 12)
    logger.debug(f"  check_EHBrI(): cond1: {cond1}")
    return cond1

def check_GemBrI(person:Person):
    """TODO: nicht genutzt"""
    pass



def get_index_match(iterable, pattern):
    """helper für Suche nach regulärem Ausdruck"""
    for index, item in enumerate(iterable):
        m = re.match(pattern, item, re.IGNORECASE)
        if m:
            return index, m.groups()
    return -1, None

def build_table_fom_csv(inputfile):
    """Personendaten aus CSV Datei auslesen.
       Die CSV Datei ist kompatibel zu dem Datenexport aus FeuerON.
       Auslesen von Grundlegenden Personendaten, Lehrgängen, Ämtern, Dienstgraden und Abteilungszugehörigkeiten"""
    try:
        logger.debug("Lese Daten von: " + str(inputfile))
        with open(inputfile, "r") as fp:
            df = pd.read_csv(fp, sep=";", encoding="utf-8")
    except:
        logger.error("Fehler beim Einlesen der Daten", sys.exc_info()[0])
        parser.print_usage()
        raise
    persons = []
    columnNames = df.columns.values

    for i, row in df.iterrows():
        p = Person(Vorname=row['Vorname'],
                   Nachname=row['Nachname'],
                   Geburtsdatum=datetime.strptime(row['Geburtsdatum'],"%d.%m.%Y"),
                   Geschlecht=row['Geschlecht'],
                   PersonalNr=row['Personal-Nr.'],)

        if isinstance(row['Einstellungsdatum'],str):
            p.Einstellungsdatum = datetime.strptime(row['Einstellungsdatum'],"%d.%m.%Y")
        logger.debug(f"Lese Datensatz: {p.PersonalNr}")
        # Keine persönlichen Daten ausgeben.
        # logger.debug(f"Lese Datensatz: {p.Nachname}, {p.Vorname}, (Geb. {row['Geburtsdatum']})")

        # Abteilungen herausfiltern
        idx_name=0
        logger.debug(f"  Abteilung_<n>[<Spalte>]: <Wert>;  von[<Spalte>]: <Wert>>;  bis[<Spalte>]: <Wert>")
        while True:
            idx,groups_art = get_index_match(columnNames[idx_name:], r'(Art/Abteilung) ([0-9]+)')
            idx_name+=idx
            if groups_art and isinstance(row.iloc[idx_name], str):
                #group_0 = groups_art[0] # 'Art/Abteilung'
                lfd_nr = groups_art[1]   # '1'
                idx_von, groups_von = get_index_match(columnNames[idx_name:], fr'Von {lfd_nr}')
                idx_bis, groups_bis = get_index_match(columnNames[idx_name:], fr'Bis {lfd_nr}')
                start = datetime.strptime(row.iloc[idx_name+idx_von],"%d.%m.%Y")
                if isinstance(row.iloc[idx_name+idx_bis],str):
                    ende = datetime.strptime(row.iloc[idx_name+idx_bis],"%d.%m.%Y")
                else:
                    ende = now
                logger.debug(f"  Abteilung_{lfd_nr}[{idx_name}]: {row.iloc[idx_name]};  von[{idx_name+idx_von}]: {row.iloc[idx_name+idx_von]};  bis[{idx_name+idx_bis}]: {row.iloc[idx_name+idx_bis]}")
                Abt = Abteilung(name=row.iloc[idx_name], von=start, bis=ende)
                p.Abteilungen.append(Abt)
                idx_name += 1
            else: break
        p.Abteilungen = sorted(p.Abteilungen, key=lambda abt: abt.bis)

        # Dienstgrad herausfiltern
        idx_name=0
        while True:
            idx,groups_art = get_index_match(columnNames[idx_name:], r'(Abk. Dienstgrad) ([0-9]+)')
            idx_name+=idx
            if groups_art and isinstance(row.iloc[idx_name], str):
                #group_0 = groups_art[0] # 'Abk. Dienstgrad'
                lfd_nr = groups_art[1]   # '1'
                idx_von, groups_von = get_index_match(columnNames[idx_name:], fr'Von {lfd_nr}')
                idx_bis, groups_bis = get_index_match(columnNames[idx_name:], fr'Bis {lfd_nr}')
                start = datetime.strptime(row.iloc[idx_name+idx_von],"%d.%m.%Y")
                if isinstance(row.iloc[idx_name+idx_bis],str):
                    ende = datetime.strptime(row.iloc[idx_name+idx_bis],"%d.%m.%Y")
                else:
                    ende = now
                logger.debug(f"  Dienstgrad_{lfd_nr}[{idx_name}]: {row.iloc[idx_name]};  von[{idx_name + idx_von}]: {row.iloc[idx_name + idx_von]};  bis[{idx_name + idx_bis}]: {row.iloc[idx_name + idx_bis]}")
                dienstgrad = Dienstgrad(name=row.iloc[idx_name], von=start, bis=ende)
                p.Dienstgrade.append(dienstgrad)
                idx_name += 1
            else: break
        if len(p.Dienstgrade)==0:
            logger.warning(f"Kein Dienstgrad eingetragen für {p.Nachname},{p.Vorname}. Schreibe {Dienstgrad.Reihenfolge_M_neu[0]} von {now.strftime("%d.%m.%Y")} bis {now.strftime("%d.%m.%Y")}")
            p.Dienstgrade.append(Dienstgrad(name=Dienstgrad.Reihenfolge_M_neu[0], von=now, bis=now))
        p.Dienstgrade = sorted(p.Dienstgrade, key=lambda dg: dg.bis)

        # Dienststellung herausfiltern
        idx_name=0
        while True:
            idx,groups_art = get_index_match(columnNames[idx_name:], r'(Dienststellung) ([0-9]+)')
            idx_name+=idx
            if groups_art and isinstance(row.iloc[idx_name], str):
                #group_0 = groups_art[0] # 'Dienststellung'
                lfd_nr = groups_art[1]   # '1'
                idx_von, groups_von = get_index_match(columnNames[idx_name:], fr'Von {lfd_nr}')
                idx_bis, groups_bis = get_index_match(columnNames[idx_name:], fr'Bis {lfd_nr}')
                start = datetime.strptime(row.iloc[idx_name+idx_von],"%d.%m.%Y")
                if isinstance(row.iloc[idx_name+idx_bis],str):
                    ende = datetime.strptime(row.iloc[idx_name+idx_bis],"%d.%m.%Y")
                else:
                    ende = now
                logger.debug( f"  Dienststellung_{lfd_nr}[{idx_name}]: {row.iloc[idx_name]};  von[{idx_name + idx_von}]: {row.iloc[idx_name + idx_von]};  bis[{idx_name + idx_bis}]: {row.iloc[idx_name + idx_bis]}")
                amt = Amt(name=row.iloc[idx_name], von=start, bis=ende)
                p.Amter.append(amt)
                idx_name += 1
            else: break

        # Lehrgang herausfiltern
        idx_name = 0
        while True:
            idx, groups_art = get_index_match(columnNames[idx_name:], r'(Lehrgangsbezeichnung) ([0-9]+)')
            idx_name += idx
            if groups_art and isinstance(row.iloc[idx_name], str):
                # group_0 = groups_art[0] # 'Lehrgangsbezeichnung'
                lfd_nr = groups_art[1]  # '1'
                idx_von, groups_von = get_index_match(columnNames[idx_name:], fr'Von {lfd_nr}')
                idx_bis, groups_bis = get_index_match(columnNames[idx_name:], fr'Bis {lfd_nr}')
                idx_status, groups_status = get_index_match(columnNames[idx_name:], fr'Status {lfd_nr}')
                start = datetime.strptime(row.iloc[idx_name + idx_von], "%d.%m.%Y")
                if isinstance(row.iloc[idx_name + idx_bis], str):
                    ende = datetime.strptime(row.iloc[idx_name + idx_bis], "%d.%m.%Y")
                else:
                    ende = now
                if isinstance(row.iloc[idx_name+idx_status],float):
                    logger.warning(f"{p.PersonalNr}: Lehrgang {lfd_nr} ist ohne Status (bestanden).")
                    #logger.warning(f"{p.Vorname}, {p.Nachname} Lehrgang {lfd_nr} ist ohne Status (bestanden).") #Keine persönlichen Daten loggen
                logger.debug( f"  Lehrgang_{lfd_nr}[{idx_name}]: {row.iloc[idx_name]};  von[{idx_name + idx_von}]: {row.iloc[idx_name + idx_von]};  bis[{idx_name + idx_bis}]: {row.iloc[idx_name + idx_bis]}")
                lehrgang = Lehrgang(name=row.iloc[idx_name], von=start, bis=ende, bestanden=row.iloc[idx_name+idx_status])
                p.Lehrgange.append(lehrgang)
                idx_name += 1
            else:
                break
        persons.append(p)
    return persons

def main(inputfile:Path, outputfile:Path):
    """main function"""
    persons = build_table_fom_csv(inputfile)

    #Der Key entspricht den Elementen von Dienstgrad.Reihenfolge_M
    dg_checkfunktions = {"FM": check_FM,
                         "OFM": check_OFM,
                         "HFM": check_HFM,
                         "EHFM": check_EHFM,
                         "BM": check_BM,
                         "OBM": check_OBM,
                         "HBM": check_HBM,
                         "EHBM": check_EHBM,
                         "BrI": check_BrI,
                         "OBrI": check_OBrI,
                         "HBrI": check_HBrI,
                         "EHBrI": check_EHBrI,
                         "GemBrI": check_GemBrI,}

    # Ausgabetabelle der Daten vorbereiten:
    outputframe = pd.DataFrame(columns=["Nachname", "Vorname", "akt. Dienstgrad", "Erfüllt Voraussetzungen für", "Dienstzeit insg.", f"Stichtag:{now.strftime('%d.%m.%Y')}"])

    # Prüfen der Beförderungsbedingungen für alle Personen
    for p in persons:
        erfuelltBedingung = []
        akt_DG = p.Dienstgrade[-1].name
        logger.info(f"Prüfe Bedingungen für {akt_DG} {p.PersonalNr}")
        #logger.info(f"Prüfe Bedingungen für {akt_DG} {p.Nachname}, {p.Vorname}") # Keine persönlichen Daten loggen

        # Aktuellen Dienstgrad in der Liste der alten Bezeichnungen suchen.
        if akt_DG in Dienstgrad.Reihenfolge_M_alt:
            idx = Dienstgrad.Reihenfolge_M_alt.index(akt_DG)
        if akt_DG in Dienstgrad.Reihenfolge_W_alt:
            idx = Dienstgrad.Reihenfolge_W_alt.index(akt_DG)
        # Bedingungen für alle Dienstgrade oberhalb des aktuellen durchführen.
        for dg in Dienstgrad.Reihenfolge_M[idx+1:]:
            if dg_checkfunktions[dg](p):
                # Hack um auf alte Dienstgrade zurück zustellen. Kann mit den neuen Dienstgraden entfallen.
                # Dann die betreffenden Zeilen einfach löschen.
                # ----------------------------------------------------------------------------------
                idx = Dienstgrad.Reihenfolge_M.index(dg)
                dg = Dienstgrad.Reihenfolge_M_alt[idx]
                # Hack ende ------------------------------------------------------------------------
                erfuelltBedingung.append(dg)
        logger.info(f"  erfüllt Bedingungen für {erfuelltBedingung}")

        dienstzeit_gesamt = AnzJahre(p.Abteilungen)

        # Ausgabetabelle füllen:
        s = ", ".join(erfuelltBedingung)
        outputframe.loc[len(outputframe)] = [p.Nachname, p.Vorname, akt_DG, s, f"{dienstzeit_gesamt:.2f} Jahre", ""]

    # Ausgabe in Datei schreiben
    outputframe.to_csv(outputfile, index=False, sep=";", encoding="utf-8-sig", mode="w")


def parse_date(s:str) -> datetime:
    """ Parse Datums string für dd.mm.yy oder dd.mm.yyyy """
    # Datumsformatierung prüfen mit dd.mm.yy oder dd.mm.yyyy
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unbekanntes Datumsformat: {s}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--input', type=str, default='./Datenbereitstellung_Dienstgrade.csv', help="Eingangsdatensatz [CSV]")
    parser.add_argument('-o', '--output', type=str, default='./Output.csv', help="Ausgangstabelle [CSV]")
    parser.add_argument('-d', '--date', default=datetime.now().strftime("%d.%m.%Y"), type=str, help="Stichtag, zu dem die Bedingungen geprüft werden sollen. [dd.mm.yyyy]")
    parser.add_argument("--trace", default="warning", choices=["warning", "info", "debug"], help="Logging level")
    args = parser.parse_args()

    match str.lower(args.trace):
        case "debug":
            logger.setLevel(logging.DEBUG)
        case "info":
            logger.setLevel(logging.INFO)
        case _:
            logger.setLevel(logging.WARNING)

    logger.debug(f"Eingegebene Daten: Inputfile={args.input}, Outputfile={args.output}, Tracelevel={args.trace}")


    try: # wer weiß, was hier eingegeben wird... wir fangen einmal alles ab.
        if not Path(args.input).is_file():
            parser.print_help(None)
            raise FileNotFoundError(f"Datei '{args.input}' nicht gefunden.")
        else:
            now=parse_date(args.date)
            logger.info(f"Stichtag: {now.strftime('%d.%m.%Y')}")
            main(inputfile=Path(args.input), outputfile=Path(args.output))
    except Exception as e:
        logger.error(e)
        parser.print_help(None)
        with open(Path("./ErrorLog.txt"), "w") as f:
            f.write(str(e))