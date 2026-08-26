"""Text preprocessing applied to narration before it reaches any TTS engine.

Confirmed by direct listening test: Piper (and espeak-ng, which it uses for
phonemization) badly mangles a written date like "November 24th, 1971" --
the ordinal-suffix-plus-year combination trips up the number reader in a way
a bare year on its own doesn't. Spelling the date out by hand in the script
JSON works but is easy to forget (that's exactly how it shipped once
already) -- so scripts should write a specific date as DD/MM/YYYY instead,
and this module converts it to natural spoken words automatically, for
every engine, before synthesis and before caption timing is estimated.
"""
import re

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_ORDINAL_ONES = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh",
    8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth",
    14: "fourteenth", 15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth",
    19: "nineteenth", 20: "twentieth", 30: "thirtieth",
}
_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_DATE_PATTERN = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _number_to_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")


def _ordinal_word(n: int) -> str:
    if n in _ORDINAL_ONES:
        return _ORDINAL_ONES[n]
    tens, ones = divmod(n, 10)
    return f"{_TENS[tens]}-{_ORDINAL_ONES[ones]}"


def _spoken_year(year: int) -> str:
    if 2000 <= year <= 2009:
        tail = year - 2000
        return "two thousand" + (f" {_ONES[tail]}" if tail else "")
    if year % 100 == 0:
        return f"{_number_to_words(year // 100)} hundred"
    return f"{_number_to_words(year // 100)} {_number_to_words(year % 100)}"


def normalize_dates_for_speech(text: str) -> str:
    """Replaces every DD/MM/YYYY date in `text` with a spoken-word form, e.g.
    "24/11/1971" -> "the twenty-fourth of November, nineteen seventy one".
    Leaves anything that isn't a plausible calendar date untouched.
    """

    def replace(match: re.Match) -> str:
        day, month, year = (int(g) for g in match.groups())
        if not (1 <= day <= 31 and 1 <= month <= 12):
            return match.group(0)
        return f"the {_ordinal_word(day)} of {_MONTHS[month - 1]}, {_spoken_year(year)}"

    return _DATE_PATTERN.sub(replace, text)
