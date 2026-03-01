from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd
import faker
import babel.dates

# This file will contain the scripts for anonymizing spans

import string
import random
from typing import Callable, Dict, List, Tuple


from meta import Span


lowers: str = string.ascii_lowercase
uppers: str = string.ascii_uppercase
numbers: str = "0123456789"


def anonymizeSpans(anonymizer : Anonymizer, spans: List[Span], text: str) -> Tuple[List[Span], str]:
    new_spans = []
    offset = 0
    for span in spans:
        span["start"]+= offset
        span["end"]+= offset
        new_span, new_text = anonymizer.anonymize(span, text)
        text = new_text
        offset += new_span["end"] - span["end"]
        new_spans.append(new_span)
    return (new_spans, text)


def _random_replace(text : str) -> str:
    new_text: List[str] = []
    for char in text:
        if char.isnumeric():
            new_text.append(random.choice(numbers))
        elif char.isalpha():
            if char.isupper():
                new_text.append(random.choice(uppers))
            else:
                new_text.append(random.choice(lowers))
        else:
            new_text.append(char)
    return "".join(new_text)

class Anonymizer(ABC):

    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def anonymize(self, span: Span, text: str) -> Tuple[Span, str]:
        pass


class RandomAnonym(Anonymizer):

    def __init__(self) -> None:
        super().__init__()

    def anonymize(self, span: Span, text: str) -> Tuple[Span, str]:
        start: int = span['start']
        end: int = span['end']
        new_text: List[str] = []
        for char in text[start:end]:
            if char.isnumeric():
                new_text.append(random.choice(numbers))
            elif char.isalpha():
                if char.isupper():
                    new_text.append(random.choice(uppers))
                else:
                    new_text.append(random.choice(lowers))
            else:
                new_text.append(char)
        return (span.copy(), text[:start] + "".join(new_text) + text[end:])

class LabelAnonym(Anonymizer):

    def __init__(self) -> None:
        super().__init__()

    def anonymize(self, span: Span, text: str) -> Tuple[Span, str]:
        start: int = span['start']
        end: int = span['end']
        label = span["label"]
        new_text: str = f"<{label}>"
        new_span = span.copy()
        new_span["end"] = new_span["start"] + len(new_text)
        return (new_span, text[:start] + new_text + text[end:])


class AllAnonym(Anonymizer):
    def __init__(self) -> None:
        super().__init__()
        """Anonymizer tuned for Spanish/Catalan by default.

        This repo was originally built for ES/CAT civic texts. For a Chilean
        deployment we want realistic CL-looking replacements (names, addresses,
        phones, etc.). The quickest robust approach is Faker with locale
        `es_CL`, plus regex detectors for CL identifiers (RUT, phones, plates).

        We keep the old gazetteer files as an optional fallback if they exist,
        but the default replacement strategy uses Faker Chile.
        """

        # Faker Chile (fallback to default Faker if locale isn't available)
        try:
            self.fake = faker.Faker("es_CL")
        except Exception:
            self.fake = faker.Faker()

        # Optional legacy gazetteers (used only as fallback)
        self._name_list = []
        self._surname_list = []
        self._barrios = []
        self.streets = None
        self.parks = None

        try:
            names_path = "data/names/names_no_rep.txt"
            surnames_path = "data/names/surnames.txt"
            with open(names_path, "r") as f:
                self._name_list = [line.strip() for line in f if line.strip()]
            with open(surnames_path, "r") as f:
                self._surname_list = [line.strip() for line in f if line.strip()]

            nomenclator_path = "data/nomenclator.csv"
            barrios_path = "data/distritos_barrios.txt"
            self._nomenclator = pd.read_csv(nomenclator_path)
            with open(barrios_path, "r") as f:
                self._barrios = [x.strip() for x in f.read().splitlines() if x.strip()]

            # Select specific locations (legacy)
            self.streets = self._nomenclator.loc[self._nomenclator['TIPUS_VIA'].isin(
                ["carrer", "via", "carreró", "avinguda", "passeig"])]
            self.parks = self._nomenclator.loc[self._nomenclator["TIPUS_VIA"].isin(
                ["jardí", "placeta", "plaça", "jardins", "parc"])]
        except Exception:
            # If files are missing, keep Faker-only behavior.
            pass

        self.replace_dict: Dict[str, Callable[[str], str]] = {
            "PER": self._replacePER,
            "LOC": self._replaceLOC,
            "DATE": self._replaceDATE,
            "ZIP": self._replaceZIP,
            "ID": self._replaceID,
            "FINANCIAL": self._replaceFINANCIAL,
            "VEHICLE": self._replaceVEHICLE,
            "CARD": self._replaceCARD,
            "TELEPHONE": self._replaceTELEPHONE,
            # Chile-specific labels (added via regex_definition.csv)
            "RUT_CL": self._replaceRUT_CL,
            "PHONE_CL": self._replacePHONE_CL,
            "LICENSE_PLATE_CL": self._replaceLICENSE_PLATE_CL,
            "OTHER": self._replaceDefault,
            "SENSITIVE": self._replaceDelete,
        }

    def anonymize(self, span: Span, text: str) -> Tuple[Span, str]:
        old_text : str = text[span["start"]:span["end"]]
        new_text = self._replaceDefault(old_text) if span["label"] not in self.replace_dict else self.replace_dict[span["label"]](old_text)
        new_span = span.copy()
        new_span["end"] = new_span["start"] + len(new_text)
        return (new_span, text[:span["start"]] + new_text + text[span["end"]:])

    def _replacePER(self, text: str) -> str:
        # Chile-tuned: generate realistic Spanish names.
        # Preserve casing style from the original token.
        replacement = self.fake.name()
        return self._format_string(text, replacement)

    def _fix_particule(self, selection) -> str:
        if type(selection['PARTICULES']) == str: # Check because some entries in nomenclator don't have particle
            if "'" in selection["PARTICULES"]:
                return f"{selection['TIPUS_VIA']} {selection['PARTICULES']}{selection['NOM']}"
            else: 
                return f"{selection['TIPUS_VIA']} {selection['PARTICULES']} {selection['NOM']}"
        else: 
            return f"{selection['TIPUS_VIA']} {selection['NOM']}"

    def _replaceLOC(self, text: str) -> str:
        # Chile-tuned: use Faker Chile address components.
        # If the legacy gazetteer is loaded and the original contains Catalan/ES
        # street markers, we still prefer Faker for CL realism.
        if any(char.isdigit() for char in text):
            address = self.fake.street_address()
        else:
            # For short locations, a city name usually reads better.
            address = self.fake.city()

        if text.isupper():
            return address.upper()
        if text.islower():
            return address.lower()
        return address

    def _replaceTELEPHONE(self, text: str) -> str:
        return text[:1] + self._replaceDefault(text[1:])

    def _replacePHONE_CL(self, text: str) -> str:
        # Format: +56 9 XXXX XXXX
        a = random.randint(1000, 9999)
        b = random.randint(1000, 9999)
        replacement = f"+56 9 {a} {b}"
        return self._format_string(text, replacement)

    def _replaceRUT_CL(self, text: str) -> str:
        # Keep a stable-looking placeholder (does not attempt checksum correctness).
        # If you later want valid DV, we can implement modulus-11.
        # Preserve punctuation style loosely by returning common RUT format.
        return "12.345.678-K"

    def _replaceLICENSE_PLATE_CL(self, text: str) -> str:
        # Common CL formats: AA-BB-11 (new) / AB-CD-12 / etc.
        letters = ''.join(random.choice(uppers) for _ in range(4))
        digits = ''.join(random.choice(numbers) for _ in range(2))
        # AB-CD-12
        replacement = f"{letters[:2]}-{letters[2:]}-{digits}"
        return self._format_string(text, replacement)

    def _replaceZIP(self, text: str) -> str:
        if text[:2].isnumeric(): # Local zip, we want to keep the first 2 digits
            return text[:2] + self._replaceDefault(text[2:])
        else:
            return self._replaceDefault(text)

    def _replaceID(self, text: str) -> str:
        return self._replaceDefault(text)

    def _replaceDATE(self, text: str) -> str:
        date = self.fake.date_time_between(start_date="-2y", end_date="now")
        if not any(map(lambda c: c.isalpha(), text)): # contracted numerical date format
            return date.strftime("%d/%m/%Y")
        # Prefer Chilean Spanish formatting
        try:
            return babel.dates.format_date(date, "long", locale="es_CL")
        except Exception:
            return babel.dates.format_date(date, "long", locale="es")

    def _replaceFINANCIAL(self, text: str) -> str:
        if text[0].isalpha(): # BANK identifier
            starting = text[:2]
            remaining = text[2:]
            replacement = _random_replace(remaining)
            return starting + replacement
        else: 
            return self._replaceDefault(text)

    def _replaceCARD(self, text: str) -> str:
        return self._replaceDefault(text)

    def _replaceVEHICLE(self, text: str) -> str:
        return self._replaceDefault(text)

    def _replaceDefault(self, text: str) -> str:
        return _random_replace(text)

    def _replaceDelete(self, text: str) -> str:
        return ""

    #TODO: Move all this logic to a subclass maybe?
    #-------------------------------------------------------
    @staticmethod
    def _format_string(text: str, replacement: str) -> str:
        if text[0].isupper():
            if len(text) > 1 and text[1].isupper():  # All Caps
                return replacement.upper()
            else:  # Capitalized
                return replacement.capitalize()
        else:  # All lower
            return replacement

    def generateName(self, text: str) -> str:
        if self._name_list:
            name = random.choice(self._name_list)
            return self._format_string(text, name)
        return self._format_string(text, self.fake.first_name())

    def generateSurname(self, text: str) -> str:
        if self._surname_list:
            surname = random.choice(self._surname_list)
            return self._format_string(text, surname)
        return self._format_string(text, self.fake.last_name())
    #-------------------------------------------------------

