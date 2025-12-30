"""
Translations for Best Wines Sweden
Swedish to English mappings for wine data
"""

# Flag emoji to country name mappings
FLAG_EMOJIS = {
    "🇪🇸": "Spain",
    "🇫🇷": "France",
    "🇮🇹": "Italy",
    "🇵🇹": "Portugal",
    "🇩🇪": "Germany",
    "🇦🇹": "Austria",
    "🇦🇺": "Australia",
    "🇳🇿": "New Zealand",
    "🇿🇦": "South Africa",
    "🇨🇱": "Chile",
    "🇦🇷": "Argentina",
    "🇺🇸": "USA",
    "🇬🇷": "Greece",
    "🇭🇺": "Hungary",
    "🇸🇮": "Slovenia",
    "🇭🇷": "Croatia",
    "🇷🇴": "Romania",
    "🇧🇬": "Bulgaria",
    "🇲🇩": "Moldova",
    "🇬🇪": "Georgia",
    "🇱🇧": "Lebanon",
    "🇮🇱": "Israel",
    "🇲🇦": "Morocco",
    "🇧🇷": "Brazil",
    "🇺🇾": "Uruguay",
    "🇲🇽": "Mexico",
    "🇨🇦": "Canada",
    "🇨🇭": "Switzerland",
    "🇬🇧": "United Kingdom",
    "🇸🇪": "Sweden",
}

# Swedish to English country translations
SWEDISH_COUNTRIES = {
    "Frankrike": "France",
    "Italien": "Italy",
    "Spanien": "Spain",
    "Portugal": "Portugal",
    "Tyskland": "Germany",
    "Österrike": "Austria",
    "Australien": "Australia",
    "Nya Zeeland": "New Zealand",
    "Sydafrika": "South Africa",
    "Chile": "Chile",
    "Argentina": "Argentina",
    "USA": "USA",
    "Grekland": "Greece",
    "Ungern": "Hungary",
    "Slovenien": "Slovenia",
    "Kroatien": "Croatia",
    "Rumänien": "Romania",
    "Bulgarien": "Bulgaria",
    "Moldavien": "Moldova",
    "Georgien": "Georgia",
    "Libanon": "Lebanon",
    "Israel": "Israel",
    "Marocko": "Morocco",
    "Tunisien": "Tunisia",
    "Brasilien": "Brazil",
    "Uruguay": "Uruguay",
    "Mexiko": "Mexico",
    "Kanada": "Canada",
    "Schweiz": "Switzerland",
    "Luxemburg": "Luxembourg",
    "Belgien": "Belgium",
    "Nederländerna": "Netherlands",
    "Storbritannien": "United Kingdom",
    "Irland": "Ireland",
    "Norge": "Norway",
    "Danmark": "Denmark",
    "Finland": "Finland",
    "Sverige": "Sweden",
    "Polen": "Poland",
    "Tjeckien": "Czech Republic",
    "Slovakien": "Slovakia",
    "Serbien": "Serbia",
    "Nordmakedonien": "North Macedonia",
    "Albanien": "Albania",
    "Montenegro": "Montenegro",
    "Bosnien och Hercegovina": "Bosnia and Herzegovina",
    "Turkiet": "Turkey",
    "Cypern": "Cyprus",
    "Malta": "Malta",
    "Kina": "China",
    "Japan": "Japan",
    "Indien": "India",
    "Thailand": "Thailand",
    "Vietnam": "Vietnam",
}

# Swedish to English wine style translations
SWEDISH_WINE_STYLES = {
    "Rött vin": "Red Wine",
    "Vitt vin": "White Wine",
    "Rosévin": "Rosé Wine",
    "Mousserande vin": "Sparkling Wine",
    "Dessertviner": "Dessert Wine",
    "Starkvin": "Fortified Wine",
    "Alkoholfritt": "Non-Alcoholic",
}

def translate_country(country_name: str) -> str:
    """Translate Swedish country name or flag emoji to English"""
    if not country_name:
        return country_name
    
    # Check for flag emoji first
    country_str = str(country_name).strip()
    if country_str in FLAG_EMOJIS:
        return FLAG_EMOJIS[country_str]
    
    # Check for Swedish name
    return SWEDISH_COUNTRIES.get(country_str, country_str)

def translate_wine_style(swedish_style: str) -> str:
    """Translate Swedish wine style to English"""
    if not swedish_style:
        return swedish_style
    return SWEDISH_WINE_STYLES.get(swedish_style, swedish_style)
