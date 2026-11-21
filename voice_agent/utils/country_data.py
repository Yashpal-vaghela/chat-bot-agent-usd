"""All countries / territories: ISO code | dial code | English name | extra spoken names (comma separated).
Same data the website's country_utils.js loads from restcountries.com, kept local so the bot never waits on an API.
Postal and phone rules are supplied by country_utils using regional metadata."""

_RAW = """
AF|+93|Afghanistan|kabul
AL|+355|Albania|
DZ|+213|Algeria|
AS|+1684|American Samoa|
AD|+376|Andorra|
AO|+244|Angola|
AI|+1264|Anguilla|
AG|+1268|Antigua and Barbuda|antigua
AR|+54|Argentina|buenos aires
AM|+374|Armenia|
AW|+297|Aruba|
AU|+61|Australia|
AT|+43|Austria|vienna
AZ|+994|Azerbaijan|baku
BS|+1242|Bahamas|
BH|+973|Bahrain|
BD|+880|Bangladesh|
BB|+1246|Barbados|
BY|+375|Belarus|minsk
BE|+32|Belgium|brussels,antwerp
BZ|+501|Belize|
BJ|+229|Benin|
BM|+1441|Bermuda|
BT|+975|Bhutan|thimphu
BO|+591|Bolivia|
BA|+387|Bosnia and Herzegovina|bosnia
BW|+267|Botswana|
BR|+55|Brazil|brasil,sao paulo,rio de janeiro
BN|+673|Brunei|
BG|+359|Bulgaria|sofia
BF|+226|Burkina Faso|
BI|+257|Burundi|
KH|+855|Cambodia|phnom penh
CM|+237|Cameroon|
CA|+1|Canada|
CV|+238|Cape Verde|
KY|+1345|Cayman Islands|
CF|+236|Central African Republic|
TD|+235|Chad|
CL|+56|Chile|santiago
CN|+86|China|
CO|+57|Colombia|bogota
KM|+269|Comoros|
CG|+242|Congo|republic of the congo
CD|+243|DR Congo|democratic republic of the congo,kinshasa
CR|+506|Costa Rica|
CI|+225|Ivory Coast|cote d'ivoire
HR|+385|Croatia|zagreb
CU|+53|Cuba|havana
CY|+357|Cyprus|nicosia
CZ|+420|Czech Republic|czechia,prague
DK|+45|Denmark|copenhagen
DJ|+253|Djibouti|
DM|+1767|Dominica|
DO|+1809|Dominican Republic|
EC|+593|Ecuador|quito
EG|+20|Egypt|cairo
SV|+503|El Salvador|
GQ|+240|Equatorial Guinea|
ER|+291|Eritrea|
EE|+372|Estonia|tallinn
SZ|+268|Eswatini|swaziland
ET|+251|Ethiopia|addis ababa
FJ|+679|Fiji|suva
FI|+358|Finland|helsinki
FR|+33|France|
GA|+241|Gabon|
GM|+220|Gambia|
GE|+995|Georgia|tbilisi
DE|+49|Germany|
GH|+233|Ghana|accra
GI|+350|Gibraltar|
GR|+30|Greece|athens
GL|+299|Greenland|
GD|+1473|Grenada|
GU|+1671|Guam|
GT|+502|Guatemala|
GN|+224|Guinea|
GW|+245|Guinea-Bissau|
GY|+592|Guyana|georgetown
HT|+509|Haiti|
HN|+504|Honduras|
HK|+852|Hong Kong|
HU|+36|Hungary|budapest
IS|+354|Iceland|reykjavik
IN|+91|India|
ID|+62|Indonesia|jakarta,bali
IR|+98|Iran|tehran
IQ|+964|Iraq|baghdad
IE|+353|Ireland|
IL|+972|Israel|tel aviv,jerusalem,israil,isreal
IT|+39|Italy|
JM|+1876|Jamaica|kingston
JP|+81|Japan|
JO|+962|Jordan|amman
KZ|+7|Kazakhstan|almaty
KE|+254|Kenya|
KI|+686|Kiribati|
KW|+965|Kuwait|
KG|+996|Kyrgyzstan|bishkek
LA|+856|Laos|
LV|+371|Latvia|riga
LB|+961|Lebanon|beirut
LS|+266|Lesotho|
LR|+231|Liberia|
LY|+218|Libya|tripoli
LI|+423|Liechtenstein|
LT|+370|Lithuania|vilnius
LU|+352|Luxembourg|
MO|+853|Macau|macao
MG|+261|Madagascar|
MW|+265|Malawi|
MY|+60|Malaysia|
MV|+960|Maldives|male
ML|+223|Mali|
MT|+356|Malta|
MH|+692|Marshall Islands|
MR|+222|Mauritania|
MU|+230|Mauritius|port louis
MX|+52|Mexico|mexico city
FM|+691|Micronesia|
MD|+373|Moldova|
MC|+377|Monaco|
MN|+976|Mongolia|ulaanbaatar
ME|+382|Montenegro|
MA|+212|Morocco|casablanca,rabat
MZ|+258|Mozambique|maputo
MM|+95|Myanmar|burma,yangon
NA|+264|Namibia|
NR|+674|Nauru|
NP|+977|Nepal|
NL|+31|Netherlands|
NZ|+64|New Zealand|
NI|+505|Nicaragua|
NE|+227|Niger|
NG|+234|Nigeria|lagos,abuja
KP|+850|North Korea|
MK|+389|North Macedonia|macedonia
NO|+47|Norway|oslo
OM|+968|Oman|
PK|+92|Pakistan|
PW|+680|Palau|
PS|+970|Palestine|
PA|+507|Panama|
PG|+675|Papua New Guinea|
PY|+595|Paraguay|
PE|+51|Peru|lima
PH|+63|Philippines|manila
PL|+48|Poland|warsaw
PT|+351|Portugal|lisbon
PR|+1787|Puerto Rico|
QA|+974|Qatar|
RO|+40|Romania|bucharest
RU|+7|Russia|russian federation,moscow,saint petersburg,rus,rassui,россия,रूस,રશિયા
RW|+250|Rwanda|kigali
KN|+1869|Saint Kitts and Nevis|
LC|+1758|Saint Lucia|
VC|+1784|Saint Vincent and the Grenadines|
WS|+685|Samoa|
SM|+378|San Marino|
ST|+239|Sao Tome and Principe|
SA|+966|Saudi Arabia|
SN|+221|Senegal|dakar
RS|+381|Serbia|belgrade
SC|+248|Seychelles|
SL|+232|Sierra Leone|
SG|+65|Singapore|
SK|+421|Slovakia|bratislava
SI|+386|Slovenia|
SB|+677|Solomon Islands|
SO|+252|Somalia|mogadishu
ZA|+27|South Africa|
KR|+82|South Korea|korea,seoul
SS|+211|South Sudan|
ES|+34|Spain|
LK|+94|Sri Lanka|
SD|+249|Sudan|khartoum
SR|+597|Suriname|
SE|+46|Sweden|stockholm
CH|+41|Switzerland|zurich,geneva
SY|+963|Syria|damascus
TW|+886|Taiwan|taipei
TJ|+992|Tajikistan|
TZ|+255|Tanzania|dar es salaam,zanzibar
TH|+66|Thailand|thai land,bangkok,phuket,ประเทศไทย,थाईलैंड,થાઈલેન્ડ
TL|+670|Timor-Leste|east timor
TG|+228|Togo|
TO|+676|Tonga|
TT|+1868|Trinidad and Tobago|trinidad
TN|+216|Tunisia|
TR|+90|Turkey|turkiye,istanbul,ankara
TM|+993|Turkmenistan|
TV|+688|Tuvalu|
UG|+256|Uganda|kampala
UA|+380|Ukraine|kyiv,kiev
AE|+971|United Arab Emirates|
GB|+44|United Kingdom|
US|+1|United States|
UY|+598|Uruguay|montevideo
UZ|+998|Uzbekistan|tashkent
VU|+678|Vanuatu|
VA|+379|Vatican City|
VE|+58|Venezuela|caracas
VN|+84|Vietnam|hanoi,ho chi minh
YE|+967|Yemen|
ZM|+260|Zambia|lusaka
ZW|+263|Zimbabwe|harare
"""

# ISO code -> (dial code, name, [aliases])
ALL_COUNTRIES = {}
for _line in _RAW.strip().splitlines():
    _iso, _dial, _name, _extra = (_line.split("|") + [""])[:4]
    ALL_COUNTRIES[_iso] = (_dial, _name, [a.strip() for a in _extra.split(",") if a.strip()])
