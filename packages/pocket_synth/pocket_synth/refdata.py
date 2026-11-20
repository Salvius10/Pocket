"""Reference data: banks, categories, cities, merchants, names, calendar, funds.

Everything here is either public reference information (bank IFSC prefixes, AMFI scheme
codes, public holidays) or invented. No real person's data appears anywhere.
"""
from __future__ import annotations

import hashlib
from datetime import date

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
START = date(2025, 11, 1)          # first day of generated history
END = date(2026, 11, 19)           # last day (yesterday, relative to 20 Nov 2026)

# ---------------------------------------------------------------------------
# Banks (IFSC prefixes and SMS sender codes are public; rates are approximations)
# ---------------------------------------------------------------------------
BANKS = {
    "HDFC":   dict(name="HDFC Bank", ifsc="HDFC0", sms=["HDFCBK"], card_sms=["HDFCBK"],
                   acct_len=14, rate_bps=275, cust="18002586161"),
    "SBI":    dict(name="State Bank of India", ifsc="SBIN0", sms=["SBIUPI", "SBIINB", "CBSSBI", "ATMSBI"],
                   card_sms=["SBICRD"], acct_len=11, rate_bps=250, cust="1800111109"),
    "ICICI":  dict(name="ICICI Bank", ifsc="ICIC0", sms=["ICICIT", "ICICIB"], card_sms=["ICICIT"],
                   acct_len=12, rate_bps=275, cust="18002662"),
    "AXIS":   dict(name="Axis Bank", ifsc="UTIB0", sms=["AXISBK"], card_sms=["AXISBK"],
                   acct_len=15, rate_bps=300, cust="18604195555"),
    "KOTAK":  dict(name="Kotak Mahindra Bank", ifsc="KKBK0", sms=["KOTAKB"], card_sms=["KOTAKB"],
                   acct_len=10, rate_bps=275, cust="18602662666"),
    "CANARA": dict(name="Canara Bank", ifsc="CNRB0", sms=["CANBNK"], card_sms=["CANBNK"],
                   acct_len=13, rate_bps=275, cust="18004250018"),
    "BOB":    dict(name="Bank of Baroda", ifsc="BARB0", sms=["BOBTXN", "BOBSMS"], card_sms=["BOBCRD"],
                   acct_len=14, rate_bps=275, cust="18005700"),
}

# Operator/circle prefixes seen on Indian SMS headers, and the 2025 TRAI category suffixes.
SMS_HEADER_PREFIXES = ["AD", "AX", "BZ", "BP", "CP", "JD", "JM", "VM", "VK", "TM", "QP", "DM", "IM"]
SMS_SUFFIXES = ["-S", "-T", ""]

# UPI handles used by personal VPAs (PSP app handles).
PERSONAL_HANDLES = ["okaxis", "okhdfcbank", "okicici", "oksbi", "ybl", "ibl", "axl", "ptyes",
                    "ptaxis", "pthdfc", "ptsbi", "upi", "apl", "naviaxis"]

# ---------------------------------------------------------------------------
# Categories (same ids as the data model)
# ---------------------------------------------------------------------------
CATEGORIES = [
    # id, kind, default_class, name_en
    ("salary", "income", "income", "Salary"),
    ("gig_payout", "income", "income", "Gig payouts"),
    ("business_income", "income", "income", "Business income"),
    ("allowance", "income", "income", "Allowance"),
    ("interest_income", "income", "income", "Interest"),
    ("other_income", "income", "income", "Other income"),
    ("refund", "refund", "refund", "Refund"),
    ("self_transfer", "transfer", "transfer", "Own account transfer"),
    ("card_payment", "transfer", "transfer", "Card bill payment"),
    ("group_settlement", "transfer", "transfer", "Group settle-up"),
    ("investment", "saving", "saving", "Investments"),
    ("rent", "expense", "committed", "Rent"),
    ("emi", "expense", "committed", "EMI"),
    ("utilities", "expense", "flexible", "Electricity & utilities"),
    ("mobile_internet", "expense", "flexible", "Mobile & internet"),
    ("insurance", "expense", "committed", "Insurance"),
    ("education", "expense", "flexible", "Education & fees"),
    ("subscriptions", "expense", "flexible", "Subscriptions"),
    ("groceries", "expense", "flexible", "Groceries"),
    ("food_delivery", "expense", "flexible", "Food delivery"),
    ("eating_out", "expense", "flexible", "Eating out"),
    ("transport", "expense", "flexible", "Travel & cabs"),
    ("fuel", "expense", "flexible", "Fuel"),
    ("shopping", "expense", "flexible", "Shopping"),
    ("entertainment", "expense", "flexible", "Entertainment"),
    ("health", "expense", "flexible", "Health"),
    ("personal_care", "expense", "flexible", "Personal care"),
    ("home_services", "expense", "flexible", "Home services"),
    ("travel", "expense", "flexible", "Trips"),
    ("family_support", "expense", "flexible", "Family support"),
    ("gifts_donations", "expense", "flexible", "Gifts & donations"),
    ("fees_charges", "expense", "flexible", "Bank fees & charges"),
    ("card_interest", "expense", "flexible", "Card interest"),
    ("cash_withdrawal", "expense", "flexible", "Cash withdrawal"),
    ("business_supplies", "expense", "flexible", "Business supplies"),
    ("business_expenses", "expense", "flexible", "Business expenses"),
    ("other_expense", "expense", "flexible", "Other"),
    ("uncategorised", "expense", "flexible", "Uncategorised"),
]

# ---------------------------------------------------------------------------
# Cities
# ---------------------------------------------------------------------------
# electricity board key, billing cadence, petrol ₹/litre (approx.), metro key, LPG ₹/cylinder (approx.)
CITIES = {
    "Chennai":    dict(state="TN", region="tamil", power="tneb", bill="bimonthly", petrol=100.8, metro="cmrl", lpg=868, water="metrowater",
                       areas=["Velachery", "Anna Nagar", "Tambaram", "Madipakkam", "Mylapore", "Porur", "T Nagar", "Adyar"]),
    "Coimbatore": dict(state="TN", region="tamil", power="tneb", bill="bimonthly", petrol=101.2, metro=None, lpg=871, water=None,
                       areas=["RS Puram", "Gandhipuram", "Peelamedu", "Saibaba Colony"]),
    "Madurai":    dict(state="TN", region="tamil", power="tneb", bill="bimonthly", petrol=101.0, metro=None, lpg=873, water=None,
                       areas=["Anna Nagar", "KK Nagar", "Tallakulam", "Thirunagar"]),
    "Bengaluru":  dict(state="KA", region="south", power="bescom", bill="monthly", petrol=102.9, metro="bmrcl", lpg=856, water="bwssb",
                       areas=["HSR Layout", "Koramangala", "Indiranagar", "Whitefield", "Jayanagar", "Marathahalli", "BTM Layout"]),
    "Hyderabad":  dict(state="TG", region="south", power="tgspdcl", bill="monthly", petrol=107.5, metro="hmrl", lpg=906, water=None,
                       areas=["Gachibowli", "Madhapur", "Kukatpally", "Ameerpet", "Kondapur"]),
    "Kochi":      dict(state="KL", region="south", power="kseb", bill="bimonthly", petrol=107.4, metro="kmrl", lpg=861, water=None,
                       areas=["Kakkanad", "Edappally", "Kaloor", "Vyttila"]),
    "Delhi":      dict(state="DL", region="hindi", power="bses_r", bill="monthly", petrol=94.8, metro="dmrc", lpg=853, water="djb",
                       areas=["Laxmi Nagar", "Dwarka", "Rohini", "Saket", "Mayur Vihar", "Karol Bagh"]),
    "Jaipur":     dict(state="RJ", region="hindi", power="jvvnl", bill="monthly", petrol=104.7, metro="jmrc", lpg=856, water=None,
                       areas=["Malviya Nagar", "Vaishali Nagar", "Mansarovar", "Raja Park", "C Scheme"]),
    "Lucknow":    dict(state="UP", region="hindi", power="mvvnl", bill="monthly", petrol=94.7, metro="lmrc", lpg=890, water=None,
                       areas=["Gomti Nagar", "Aliganj", "Indira Nagar", "Hazratganj"]),
    "Patna":      dict(state="BR", region="hindi", power="sbpdcl", bill="monthly", petrol=105.6, metro=None, lpg=951, water=None,
                       areas=["Kankarbagh", "Boring Road", "Rajendra Nagar", "Patliputra"]),
    "Indore":     dict(state="MP", region="hindi", power="mppkvvcl", bill="monthly", petrol=106.5, metro=None, lpg=881, water=None,
                       areas=["Vijay Nagar", "Palasia", "Rajwada", "Bhawarkuan"]),
    "Mumbai":     dict(state="MH", region="west", power="adani", bill="monthly", petrol=103.5, metro="mmone", lpg=852, water=None,
                       areas=["Andheri West", "Powai", "Goregaon", "Thane West", "Chembur", "Borivali", "Bandra West"]),
    "Pune":       dict(state="MH", region="west", power="msedcl", bill="monthly", petrol=104.1, metro="punemetro", lpg=856, water=None,
                       areas=["Kothrud", "Baner", "Hinjewadi", "Viman Nagar", "Hadapsar"]),
    "Ahmedabad":  dict(state="GJ", region="west", power="torrent", bill="monthly", petrol=94.5, metro=None, lpg=860, water=None,
                       areas=["Satellite", "Navrangpura", "Bopal", "Maninagar"]),
    "Kolkata":    dict(state="WB", region="east", power="cesc", bill="monthly", petrol=105.0, metro="kolmetro", lpg=879, water=None,
                       areas=["Salt Lake", "Behala", "New Town", "Ballygunge", "Dum Dum"]),
}

# ---------------------------------------------------------------------------
# Merchants. Fields: key|display|narration name|category|subcategory|vpa|cities|subscription
# VPAs are plausible patterns invented for this dataset, not verified merchant IDs.
# cities: '*' = everywhere; otherwise comma list.
# ---------------------------------------------------------------------------
_MERCHANTS = """
swiggy|Swiggy|SWIGGY|food_delivery||swiggyorders@axisbank|*|0
zomato|Zomato|ZOMATO LTD|food_delivery||zomato.payu@hdfcbank|*|0
eatsure|EatSure|REBEL FOODS EATSURE|food_delivery||rebelfoods@icici|*|0
box8|Box8|BOX8 DESI MEALS|food_delivery||box8@ybl|Bengaluru,Mumbai,Pune,Hyderabad,Delhi|0
dominos|Domino's Pizza|JUBILANT FOODWORKS DOMINOS|food_delivery||dominos.payu@hdfcbank|*|0
pizzahut|Pizza Hut|PIZZA HUT|food_delivery||pizzahut@icici|*|0
magicpin|magicpin|MAGICPIN|food_delivery||magicpin@ybl|Delhi,Bengaluru,Mumbai,Pune,Lucknow|0
blinkit|Blinkit|BLINKIT GROFERS INDIA|groceries||blinkit.payu@hdfcbank|*|0
zepto|Zepto|ZEPTO KIRANAKART|groceries||zeptonow.rzp@icici|*|0
instamart|Swiggy Instamart|SWIGGY INSTAMART|groceries||instamart@axisbank|*|0
bigbasket|BigBasket|INNOVATIVE RETAIL BIGBASKET|groceries||bigbasket@hdfcbank|*|0
dmart|DMart|AVENUE SUPERMARTS LTD|groceries||dmartavenue@hdfcbank|*|0
smartbazaar|Reliance Smart Bazaar|RELIANCE RETAIL SMART BAZAAR|groceries||relianceretail@icici|*|0
jiomart|JioMart|RELIANCE RETAIL JIOMART|groceries||jiomart@icici|*|0
more|More Supermarket|MORE RETAIL PVT LTD|groceries||moreretail@axisbank|*|0
spencers|Spencer's|SPENCERS RETAIL LTD|groceries||spencers@icici|Chennai,Kolkata,Hyderabad,Lucknow|0
starbazaar|Star Bazaar|TRENT HYPERMARKET STAR|groceries||starbazaar@hdfcbank|Mumbai,Pune,Bengaluru,Ahmedabad|0
naturesbasket|Nature's Basket|NATURES BASKET LTD|groceries||naturesbasket@icici|Mumbai,Pune,Bengaluru,Delhi|0
countrydelight|Country Delight|COUNTRY DELIGHT|groceries||countrydelight@ybl|Delhi,Mumbai,Bengaluru,Pune,Hyderabad,Jaipur,Chennai|0
licious|Licious|DELIGHTFUL GOURMET LICIOUS|groceries||licious@icici|*|0
freshtohome|FreshToHome|FRESHTOHOME FOODS|groceries||freshtohome@ybl|Chennai,Bengaluru,Kochi,Hyderabad,Delhi|0
aavin|Aavin|AAVIN TN COOP MILK|groceries||aavinmilk@sbi|Chennai,Coimbatore,Madurai|0
nandini|Nandini Milk Parlour|KMF NANDINI|groceries||kmfnandini@cnrb|Bengaluru|0
motherdairy|Mother Dairy|MOTHER DAIRY FRUIT AND VEG|groceries||motherdairy@icici|Delhi,Lucknow|0
amul|Amul Parlour|AMUL PARLOUR|groceries||amulparlour@ybl|*|0
nilgiris|Nilgiris Supermarket|NILGIRIS 1905|groceries||nilgiris@hdfcbank|Chennai,Bengaluru,Coimbatore|0
ratnadeep|Ratnadeep Supermarket|RATNADEEP RETAIL|groceries||ratnadeep@icici|Hyderabad|0
kannan|Kannan Departmental Store|KANNAN DEPARTMENTAL STORE|groceries||kannandept@sbi|Chennai|0
saravanabhavan|Hotel Saravana Bhavan|HOTEL SARAVANA BHAVAN|eating_out||hsb@icici|Chennai,Delhi,Mumbai,Bengaluru|0
a2b|A2B Adyar Ananda Bhavan|ADYAR ANANDA BHAVAN SWEETS|eating_out||a2bsweets@hdfcbank|Chennai,Bengaluru,Coimbatore,Madurai|0
sangeetha|Sangeetha Veg Restaurant|SANGEETHA VEG RESTAURANT|eating_out||sangeethaveg@icici|Chennai|0
muruganidli|Murugan Idli Shop|MURUGAN IDLI SHOP|eating_out||muruganidli@sbi|Chennai,Madurai|0
anjappar|Anjappar Chettinad|ANJAPPAR CHETTINAD RESTAURANT|eating_out||anjappar@hdfcbank|Chennai|0
thalappakatti|Dindigul Thalappakatti|DINDIGUL THALAPPAKATTI|eating_out||thalappakatti@icici|Chennai,Coimbatore,Madurai,Bengaluru|0
srikrishnasweets|Sri Krishna Sweets|SRI KRISHNA SWEETS|eating_out||srikrishnasweets@hdfcbank|Chennai,Coimbatore,Bengaluru|0
haldirams|Haldiram's|HALDIRAM SNACKS PVT LTD|eating_out||haldirams@icici|Delhi,Jaipur,Lucknow,Mumbai,Patna|0
bikanervala|Bikanervala|BIKANERVALA FOODS|eating_out||bikanervala@hdfcbank|Delhi,Jaipur,Lucknow|0
bittutikki|Bittu Tikki Wala|BTW BITTU TIKKI WALA|eating_out||btw@ybl|Delhi|0
rawat|Rawat Mishthan Bhandar|RAWAT MISHTHAN BHANDAR|eating_out||rawatmishthan@sbi|Jaipur|0
lmb|Laxmi Mishthan Bhandar|LAXMI MISHTHAN BHANDAR LMB|eating_out||lmbjaipur@hdfcbank|Jaipur|0
rameshwaram|The Rameshwaram Cafe|THE RAMESHWARAM CAFE|eating_out||rameshwaramcafe@icici|Bengaluru,Hyderabad,Chennai|0
vidyarthi|Vidyarthi Bhavan|VIDYARTHI BHAVAN|eating_out||vidyarthibhavan@cnrb|Bengaluru|0
meghana|Meghana Foods|MEGHANA FOODS|eating_out||meghanafoods@ybl|Bengaluru|0
truffles|Truffles|TRUFFLES ICE AND SPICE|eating_out||truffles@icici|Bengaluru|0
paradise|Paradise Biryani|PARADISE FOOD COURT|eating_out||paradisebiryani@hdfcbank|Hyderabad,Bengaluru,Chennai|0
karachibakery|Karachi Bakery|KARACHI BAKERY|eating_out||karachibakery@icici|Hyderabad|0
kailashparbat|Kailash Parbat|KAILASH PARBAT|eating_out||kailashparbat@hdfcbank|Mumbai,Pune|0
cafemadras|Cafe Madras|CAFE MADRAS|eating_out||cafemadras@ybl|Mumbai|0
theobroma|Theobroma|THEOBROMA FOODS|eating_out||theobroma@icici|Mumbai,Pune,Bengaluru,Delhi,Hyderabad|0
mcdonalds|McDonald's|HARDCASTLE RESTAURANTS MCDONALDS|eating_out||mcdonalds@hdfcbank|*|0
burgerking|Burger King|RESTAURANT BRANDS ASIA BURGER KING|eating_out||burgerking@icici|*|0
kfc|KFC|DEVYANI INTERNATIONAL KFC|eating_out||kfcindia@ybl|*|0
subway|Subway|SUBWAY|eating_out||subway@icici|*|0
starbucks|Starbucks|TATA STARBUCKS PVT LTD|eating_out||tatastarbucks@hdfcbank|Mumbai,Delhi,Bengaluru,Chennai,Hyderabad,Pune,Kolkata,Ahmedabad,Jaipur,Kochi|0
ccd|Cafe Coffee Day|COFFEE DAY GLOBAL|eating_out||cafecoffeeday@icici|*|0
chaayos|Chaayos|SUNSHINE TEAHOUSE CHAAYOS|eating_out||chaayos@ybl|Delhi,Mumbai,Bengaluru,Pune|0
chaipoint|Chai Point|MOUNTAIN TRAIL CHAI POINT|eating_out||chaipoint@icici|Bengaluru,Delhi,Chennai,Mumbai,Hyderabad|0
thirdwave|Third Wave Coffee|THIRD WAVE COFFEE ROASTERS|eating_out||thirdwave@hdfcbank|Bengaluru,Mumbai,Delhi,Pune,Hyderabad|0
bluetokai|Blue Tokai|BLUE TOKAI COFFEE|eating_out||bluetokai@icici|Delhi,Mumbai,Bengaluru|0
barbequenation|Barbeque Nation|BARBEQUE NATION HOSPITALITY|eating_out||bbqnation@hdfcbank|*|0
wowmomo|Wow! Momo|WOW MOMO FOODS|eating_out||wowmomo@ybl|*|0
socialbar|SOCIAL|IMPRESARIO SOCIAL|eating_out||impresario@icici|Bengaluru,Mumbai,Delhi,Pune,Hyderabad|0
baskinrobbins|Baskin Robbins|GRAVISS BASKIN ROBBINS|eating_out||baskinrobbins@ybl|*|0
naturalsicecream|Natural Ice Cream|NATURALS ICE CREAM|eating_out||naturalsicecream@hdfcbank|Mumbai,Pune,Bengaluru|0
uber|Uber|UBER INDIA SYSTEMS|transport||uber.rzp@icici|Chennai,Bengaluru,Hyderabad,Kochi,Delhi,Jaipur,Lucknow,Mumbai,Pune,Ahmedabad,Kolkata,Indore,Coimbatore|0
ola|Ola|ANI TECHNOLOGIES OLA|transport||olacabs.payu@hdfcbank|*|0
rapido|Rapido|ROPPEN TRANSPORTATION RAPIDO|transport||rapido@ybl|*|0
cmrl|Chennai Metro|CHENNAI METRO RAIL LTD|transport||cmrltravel@sbi|Chennai|0
bmrcl|Namma Metro|BANGALORE METRO RAIL CORP|transport||bmrcl@icici|Bengaluru|0
dmrc|Delhi Metro|DELHI METRO RAIL CORP|transport||dmrc@sbi|Delhi|0
mmone|Mumbai Metro One|MUMBAI METRO ONE PVT LTD|transport||mumbaimetro@icici|Mumbai|0
hmrl|Hyderabad Metro|L AND T METRO RAIL HYDERABAD|transport||ltmetro@icici|Hyderabad|0
kmrl|Kochi Metro|KOCHI METRO RAIL LTD|transport||kochimetro@sbi|Kochi|0
punemetro|Pune Metro|MAHA METRO PUNE|transport||mahametro@sbi|Pune|0
jmrc|Jaipur Metro|JAIPUR METRO RAIL CORP|transport||jaipurmetro@sbi|Jaipur|0
lmrc|Lucknow Metro|UP METRO RAIL CORP LUCKNOW|transport||upmrc@sbi|Lucknow|0
kolmetro|Kolkata Metro|METRO RAILWAY KOLKATA|transport||kolkatametro@sbi|Kolkata|0
fastag|FASTag recharge|NETC FASTAG RECHARGE|transport||netcfastag@icici|*|0
irctc|IRCTC|IRCTC|travel||irctc.payu@hdfcbank|*|0
redbus|redBus|REDBUS INDIA|travel||redbus@icici|*|0
abhibus|AbhiBus|ABHIBUS SERVICES|travel||abhibus@ybl|*|0
makemytrip|MakeMyTrip|MAKEMYTRIP INDIA|travel||makemytrip@icici|*|0
goibibo|Goibibo|IBIBO GROUP GOIBIBO|travel||goibibo@hdfcbank|*|0
indigo|IndiGo|INTERGLOBE AVIATION INDIGO|travel||indigo@icici|*|0
airindia|Air India|AIR INDIA LTD|travel||airindia@sbi|*|0
oyo|OYO|ORAVEL STAYS OYO|travel||oyo@icici|*|0
airbnb|Airbnb|AIRBNB PAYMENTS|travel||airbnb@hdfcbank|*|0
iocl|Indian Oil|INDIAN OIL CORPORATION|fuel||iocl@sbi|*|0
hpcl|HP Petrol Pump|HINDUSTAN PETROLEUM CORP|fuel||hpcl@icici|*|0
bpcl|Bharat Petroleum|BHARAT PETROLEUM CORP|fuel||bpcl@hdfcbank|*|0
shell|Shell|SHELL INDIA MARKETS|fuel||shellindia@icici|Bengaluru,Chennai,Mumbai,Delhi,Hyderabad,Pune|0
nayara|Nayara Energy|NAYARA ENERGY|fuel||nayara@ybl|*|0
jiobp|Jio-bp|RELIANCE BP MOBILITY JIO BP|fuel||jiobp@icici|*|0
amazon|Amazon|AMAZON PAY INDIA PVT LTD|shopping||amazonpay@apl|*|0
flipkart|Flipkart|FLIPKART INTERNET PVT LTD|shopping||flipkart@axisbank|*|0
myntra|Myntra|MYNTRA DESIGNS|shopping||myntra@icici|*|0
ajio|AJIO|RELIANCE RETAIL AJIO|shopping||ajio@icici|*|0
meesho|Meesho|FASHNEAR TECHNOLOGIES MEESHO|shopping||meesho@ybl|*|0
nykaa|Nykaa|FSN ECOMMERCE NYKAA|shopping||nykaa@icici|*|0
croma|Croma|INFINITI RETAIL CROMA|shopping||croma@hdfcbank|*|0
reliancedigital|Reliance Digital|RELIANCE DIGITAL RETAIL|shopping||reliancedigital@icici|*|0
vijaysales|Vijay Sales|VIJAY SALES|shopping||vijaysales@hdfcbank|Mumbai,Pune,Delhi,Ahmedabad,Hyderabad,Bengaluru|0
decathlon|Decathlon|DECATHLON SPORTS INDIA|shopping||decathlon@icici|*|0
lifestyle|Lifestyle|LIFESTYLE INTERNATIONAL|shopping||lifestylestores@hdfcbank|*|0
westside|Westside|TRENT LTD WESTSIDE|shopping||westside@icici|*|0
zudio|Zudio|TRENT LTD ZUDIO|shopping||zudio@icici|*|0
pantaloons|Pantaloons|ABFRL PANTALOONS|shopping||pantaloons@hdfcbank|*|0
maxfashion|Max Fashion|LANDMARK MAX FASHION|shopping||maxfashion@icici|*|0
hm|H&M|H AND M HENNES MAURITZ|shopping||hmindia@hdfcbank|Mumbai,Delhi,Bengaluru,Chennai,Hyderabad,Pune,Kolkata,Jaipur,Lucknow,Ahmedabad,Kochi|0
uniqlo|Uniqlo|UNIQLO INDIA|shopping||uniqlo@icici|Delhi,Mumbai,Bengaluru|0
ikea|IKEA|IKEA INDIA PVT LTD|shopping||ikeaindia@hdfcbank|Hyderabad,Mumbai,Bengaluru|0
pepperfry|Pepperfry|PEPPERFRY LTD|shopping||pepperfry@icici|*|0
lenskart|Lenskart|LENSKART SOLUTIONS|shopping||lenskart@ybl|*|0
tanishq|Tanishq|TITAN COMPANY TANISHQ|shopping||tanishq@hdfcbank|*|0
pothys|Pothys|POTHYS PVT LTD|shopping||pothys@sbi|Chennai,Coimbatore,Madurai|0
nalli|Nalli Silks|NALLI CHINNASAMI CHETTY|shopping||nallisilks@icici|Chennai,Bengaluru|0
saravanastores|Saravana Stores|SARAVANA STORES|shopping||saravanastores@sbi|Chennai|0
chennaisilks|The Chennai Silks|THE CHENNAI SILKS|shopping||chennaisilks@hdfcbank|Chennai,Coimbatore,Madurai,Bengaluru|0
firstcry|FirstCry|BRAINBEES FIRSTCRY|shopping||firstcry@icici|*|0
bata|Bata|BATA INDIA LTD|shopping||bataindia@hdfcbank|*|0
boat|boAt|IMAGINE MARKETING BOAT|shopping||boatlifestyle@icici|*|0
trends|Reliance Trends|RELIANCE RETAIL TRENDS|shopping||reliancetrends@icici|*|0
fabindia|Fabindia|FABINDIA LTD|shopping||fabindia@hdfcbank|*|0
bookmyshow|BookMyShow|BIGTREE ENTERTAINMENT BOOKMYSHOW|entertainment||bookmyshow@icici|*|0
pvrinox|PVR INOX|PVR INOX LTD|entertainment||pvrinox@hdfcbank|*|0
district|District|DISTRICT BY ZOMATO|entertainment||districtapp@hdfcbank|*|0
wonderla|Wonderla|WONDERLA HOLIDAYS|entertainment||wonderla@icici|Bengaluru,Kochi,Hyderabad,Chennai|0
timezone|Timezone|TIMEZONE ENTERTAINMENT|entertainment||timezone@icici|*|0
steam|Steam|VALVE STEAM GAMES|entertainment||steam@icici|*|0
netflix|Netflix|NETFLIX ENTERTAINMENT SERVICES|subscriptions|ott|netflixupi.payu@hdfcbank|*|1
primevideo|Amazon Prime|AMAZON PRIME|subscriptions|ott|amazonprime@apl|*|1
jiohotstar|JioHotstar|JIOSTAR INDIA JIOHOTSTAR|subscriptions|ott|jiohotstar@icici|*|1
sonyliv|Sony LIV|CULVER MAX SONY LIV|subscriptions|ott|sonyliv@icici|*|1
zee5|ZEE5|ZEE ENTERTAINMENT ZEE5|subscriptions|ott|zee5@hdfcbank|*|1
aha|aha|ARHA MEDIA AHA|subscriptions|ott|ahavideo@icici|*|1
sunnxt|Sun NXT|SUN TV NETWORK SUN NXT|subscriptions|ott|sunnxt@icici|*|1
spotify|Spotify|SPOTIFY INDIA|subscriptions|music|spotify.rzp@icici|*|1
youtubepremium|YouTube Premium|GOOGLE YOUTUBE PREMIUM|subscriptions|music|googleyoutube@okicici|*|1
jiosaavn|JioSaavn|SAAVN MEDIA JIOSAAVN|subscriptions|music|jiosaavn@icici|*|1
applemedia|Apple Media Services|APPLE MEDIA SERVICES|subscriptions|cloud|applemedia@hdfcbank|*|1
googleone|Google One|GOOGLE ONE|subscriptions|cloud|googleone@okicici|*|1
googleplay|Google Play|GOOGLE PLAY|subscriptions|apps|googleplay@okicici|*|1
audible|Audible|AUDIBLE INDIA|subscriptions|books|audible@apl|*|1
kindleunlimited|Kindle Unlimited|AMAZON KINDLE UNLIMITED|subscriptions|books|kindle@apl|*|1
microsoft365|Microsoft 365|MICROSOFT INDIA 365|subscriptions|apps|microsoft365@icici|*|1
linkedin|LinkedIn Premium|LINKEDIN PREMIUM|subscriptions|career|linkedin@icici|*|1
timesprime|Times Prime|TIMES INTERNET TIMES PRIME|subscriptions|news|timesprime@icici|*|1
thehindu|The Hindu Digital|THG PUBLISHING THE HINDU|subscriptions|news|thehindu@icici|*|1
cultfit|cult.fit|CUREFIT HEALTHCARE CULT|subscriptions|fitness|cultfit@icici|Bengaluru,Mumbai,Delhi,Hyderabad,Chennai,Pune,Jaipur,Lucknow,Kolkata,Ahmedabad|1
duolingo|Duolingo|DUOLINGO|subscriptions|apps|duolingo@icici|*|1
openai|ChatGPT Plus|OPENAI CHATGPT SUBSCR|subscriptions|apps|openai@icici|*|1
jio|Jio Prepaid|RELIANCE JIO INFOCOMM|mobile_internet||jioprepaid@ybl|*|0
airtel|Airtel|BHARTI AIRTEL LTD|mobile_internet||airtelpayments@airtel|*|0
vi|Vi|VODAFONE IDEA LTD|mobile_internet||vimobile@icici|*|0
bsnl|BSNL|BHARAT SANCHAR NIGAM LTD|mobile_internet||bsnl@sbi|*|0
jiofiber|JioFiber|RELIANCE JIO JIOFIBER|mobile_internet||jiofiber@ybl|*|0
airtelfiber|Airtel Xstream Fiber|BHARTI AIRTEL XSTREAM FIBER|mobile_internet||airtelxstream@airtel|*|0
act|ACT Fibernet|ATRIA CONVERGENCE ACT|mobile_internet||actfibernet@icici|Bengaluru,Chennai,Hyderabad,Delhi,Coimbatore,Madurai|0
hathway|Hathway|HATHWAY CABLE DATACOM|mobile_internet||hathway@icici|Mumbai,Pune,Bengaluru,Hyderabad,Chennai,Kolkata|0
excitel|Excitel|EXCITEL BROADBAND|mobile_internet||excitel@icici|Delhi,Jaipur,Lucknow,Hyderabad,Mumbai|0
tataplay|Tata Play|TATA PLAY LTD DTH|mobile_internet||tataplay@icici|*|0
tneb|TNEB electricity|TNPDCL TNEB ELECTRICITY|utilities||tneb.bbps@sbi|Chennai,Coimbatore,Madurai|0
bescom|BESCOM|BANGALORE ELECTRICITY SUPPLY CO|utilities||bescom.bbps@icici|Bengaluru|0
bses_r|BSES Rajdhani|BSES RAJDHANI POWER LTD|utilities||bsesrajdhani@icici|Delhi|0
bses_y|BSES Yamuna|BSES YAMUNA POWER LTD|utilities||bsesyamuna@icici|Delhi|0
tpddl|Tata Power-DDL|TATA POWER DELHI DISTRIBUTION|utilities||tpddl@icici|Delhi|0
jvvnl|JVVNL|JAIPUR VIDYUT VITRAN NIGAM|utilities||jvvnl.bbps@sbi|Jaipur|0
adani|Adani Electricity|ADANI ELECTRICITY MUMBAI LTD|utilities||adanielectricity@icici|Mumbai|0
best|BEST electricity|BEST UNDERTAKING|utilities||bestundertaking@sbi|Mumbai|0
tgspdcl|TGSPDCL|TG SOUTHERN POWER DISTRIBUTION|utilities||tgspdcl@sbi|Hyderabad|0
msedcl|MSEDCL Mahavitaran|MAHARASHTRA STATE ELECTRICITY DIST|utilities||msedcl@sbi|Pune|0
cesc|CESC|CESC LIMITED|utilities||cesc@icici|Kolkata|0
mvvnl|UPPCL (MVVNL)|MADHYANCHAL VIDYUT VITRAN NIGAM|utilities||uppcl@sbi|Lucknow|0
kseb|KSEB|KERALA STATE ELECTRICITY BOARD|utilities||kseb@sbi|Kochi|0
torrent|Torrent Power|TORRENT POWER LTD|utilities||torrentpower@icici|Ahmedabad|0
mppkvvcl|MP Paschim Kshetra Vidyut|MP PASCHIM KSHETRA VVCL|utilities||mppkvvcl@sbi|Indore|0
sbpdcl|SBPDCL|SOUTH BIHAR POWER DISTRIBUTION|utilities||sbpdcl@sbi|Patna|0
indane|Indane Gas|INDIAN OIL INDANE LPG|utilities||indanegas@sbi|*|0
hpgas|HP Gas|HINDUSTAN PETROLEUM HP GAS|utilities||hpgas@icici|*|0
bharatgas|Bharatgas|BHARAT PETROLEUM BHARATGAS|utilities||bharatgas@hdfcbank|*|0
mgl|Mahanagar Gas|MAHANAGAR GAS LTD|utilities||mahanagargas@icici|Mumbai|0
igl|Indraprastha Gas|INDRAPRASTHA GAS LTD|utilities||iglonline@icici|Delhi|0
metrowater|Chennai Metrowater|CHENNAI METRO WATER SUPPLY|utilities||cmwssb@sbi|Chennai|0
bwssb|BWSSB|BANGALORE WATER SUPPLY SEWERAGE|utilities||bwssb@sbi|Bengaluru|0
djb|Delhi Jal Board|DELHI JAL BOARD|utilities||delhijalboard@sbi|Delhi|0
apollopharmacy|Apollo Pharmacy|APOLLO PHARMACIES LTD|health||apollopharmacy@icici|*|0
medplus|MedPlus|OPTIVAL HEALTH MEDPLUS|health||medplus@hdfcbank|*|0
netmeds|Netmeds|NETMEDS MARKETPLACE|health||netmeds@icici|*|0
pharmeasy|PharmEasy|AXELIA SOLUTIONS PHARMEASY|health||pharmeasy@ybl|*|0
tata1mg|Tata 1mg|TATA 1MG HEALTHCARE|health||tata1mg@icici|*|0
practo|Practo|PRACTO TECHNOLOGIES|health||practo@icici|*|0
apollohospitals|Apollo Hospitals|APOLLO HOSPITALS ENTERPRISE|health||apollohospitals@hdfcbank|Chennai,Bengaluru,Hyderabad,Delhi,Mumbai,Kolkata,Ahmedabad,Madurai,Lucknow,Kochi,Indore|0
lalpathlabs|Dr Lal PathLabs|DR LAL PATHLABS|health||lalpathlabs@icici|*|0
thyrocare|Thyrocare|THYROCARE TECHNOLOGIES|health||thyrocare@ybl|*|0
wellnessforever|Wellness Forever|WELLNESS FOREVER MEDICARE|health||wellnessforever@hdfcbank|Mumbai,Pune|0
naturals|Naturals Salon|NATURALS SALON AND SPA|personal_care||naturalssalon@icici|*|0
greentrends|Green Trends|GREEN TRENDS UNISEX SALON|personal_care||greentrends@icici|Chennai,Bengaluru,Coimbatore,Madurai,Hyderabad,Kochi|0
lakmesalon|Lakme Salon|LAKME SALON|personal_care||lakmesalon@hdfcbank|*|0
urbancompany|Urban Company|URBANCLAP TECHNOLOGIES|home_services||urbancompany@icici|*|0
tumbledry|Tumbledry|TUMBLEDRY SOLUTIONS|home_services||tumbledry@ybl|*|0
physicswallah|Physics Wallah|PHYSICSWALLAH LTD|education||physicswallah@icici|*|0
unacademy|Unacademy|SORTING HAT UNACADEMY|education||unacademy@icici|*|0
allen|Allen Career Institute|ALLEN CAREER INSTITUTE|education||allenkota@sbi|Jaipur,Delhi,Lucknow,Patna,Indore,Kolkata|0
aakash|Aakash Institute|AAKASH EDUCATIONAL SERVICES|education||aakash@icici|Delhi,Patna,Lucknow,Kolkata,Jaipur,Chennai|0
coursera|Coursera|COURSERA|education||coursera@icici|*|0
udemy|Udemy|UDEMY|education||udemy@icici|*|0
sbcollect|SB Collect|SBI COLLECT|education||sbcollect@sbi|*|0
lic|LIC of India|LIFE INSURANCE CORPORATION OF INDIA|insurance||licofindia@sbi|*|0
hdfclife|HDFC Life|HDFC LIFE INSURANCE|insurance||hdfclife@hdfcbank|*|0
iciciprulife|ICICI Prudential Life|ICICI PRUDENTIAL LIFE INSURANCE|insurance||iciciprulife@icici|*|0
sbilife|SBI Life|SBI LIFE INSURANCE|insurance||sbilife@sbi|*|0
starhealth|Star Health|STAR HEALTH AND ALLIED INSURANCE|insurance||starhealth@icici|*|0
nivabupa|Niva Bupa|NIVA BUPA HEALTH INSURANCE|insurance||nivabupa@icici|*|0
carehealth|Care Health|CARE HEALTH INSURANCE|insurance||carehealth@icici|*|0
acko|Acko|ACKO GENERAL INSURANCE|insurance||acko@icici|*|0
digit|Digit Insurance|GO DIGIT GENERAL INSURANCE|insurance||godigit@icici|*|0
policybazaar|PolicyBazaar|PB FINTECH POLICYBAZAAR|insurance||policybazaar@icici|*|0
iccl|BSE StAR MF (ICCL)|INDIAN CLEARING CORP LTD|investment||iccl@icici|*|0
nsccl|NSE Clearing (NMF II)|NSE CLEARING LTD|investment||nsccl@hdfcbank|*|0
zerodha|Zerodha|ZERODHA BROKING LTD|investment||zerodha@hdfcbank|*|0
groww|Groww|NEXTBILLION GROWW|investment||groww@icici|*|0
cams|CAMS|COMPUTER AGE MANAGEMENT SERVICES|investment||camsonline@icici|*|0
kfintech|KFintech|KFIN TECHNOLOGIES|investment||kfintech@icici|*|0
bajajfinance|Bajaj Finance|BAJAJ FINANCE LTD|emi||bajajfinance@icici|*|0
herofincorp|Hero FinCorp|HERO FINCORP LTD|emi||herofincorp@icici|*|0
tvscredit|TVS Credit|TVS CREDIT SERVICES|emi||tvscredit@icici|*|0
tatacapital|Tata Capital|TATA CAPITAL LTD|emi||tatacapital@icici|*|0
homecredit|Home Credit|HOME CREDIT INDIA FINANCE|emi||homecredit@icici|*|0
cred|CRED|DREAMPLUG TECHNOLOGIES CRED|card_payment||cred.club@axisb|*|0
billdesk|BillDesk|BILLDESK CARD PAYMENT|card_payment||billdesk@hdfcbank|*|0
metrocc|Metro Cash & Carry|METRO CASH AND CARRY INDIA|business_supplies||metrocashcarry@icici|Jaipur,Delhi,Bengaluru,Mumbai,Hyderabad,Kolkata,Lucknow,Ahmedabad,Indore,Chennai,Pune|0
udaan|Udaan|HIVELOOP UDAAN|business_supplies||udaan@icici|*|0
jumbotail|Jumbotail|JUMBOTAIL TECHNOLOGIES|business_supplies||jumbotail@icici|Bengaluru,Hyderabad,Chennai,Jaipur,Delhi|0
phonepe_biz|PhonePe settlement|PHONEPE PVT LTD|business_income||phonepe.settlement@ybl|*|0
paytm_biz|Paytm settlement|PAYTM PAYMENTS SERVICES|business_income||paytm.settlement@ptys|*|0
pinelabs|Pine Labs settlement|PINE LABS PVT LTD|business_income||pinelabs@icici|*|0
zomato_payout|Zomato partner payout|ZOMATO LTD DELIVERY PARTNER|gig_payout||zomatopartner@hdfcbank|*|0
swiggy_payout|Swiggy partner payout|SWIGGY LTD DE PAYOUT|gig_payout||swiggypartner@axisbank|*|0
rapido_payout|Rapido captain payout|ROPPEN TRANSPORTATION CAPTAIN|gig_payout||rapidocaptain@ybl|*|0
uber_payout|Uber driver payout|UBER INDIA DRIVER PAYOUT|gig_payout||uberdriver@icici|*|0
blinkit_payout|Blinkit partner payout|BLINKIT COMMERCE PARTNER|gig_payout||blinkitpartner@hdfcbank|*|0
fnp|Ferns N Petals|FERNS N PETALS|gifts_donations||fernsnpetals@icici|*|0
igp|IGP|IGP COM|gifts_donations||igpgifts@icici|*|0
giveindia|GiveIndia|GIVE FOUNDATION|gifts_donations||giveindia@icici|*|0
cry|CRY|CHILD RIGHTS AND YOU|gifts_donations||cryindia@icici|*|0
"""

# Neighbourhood merchants that are common enough to be in our merchant table (invented names).
_LOCAL = {
    "Chennai":    [("Sri Murugan Stores", "groceries"), ("Ganesh Tea Stall", "eating_out"), ("Velachery Fresh Vegetables", "groceries"),
                   ("Sri Balaji Medicals", "health"), ("Classic Gents Salon", "personal_care"), ("Annapoorna Mess", "eating_out")],
    "Coimbatore": [("Sri Annapoorna Stores", "groceries"), ("Kovai Tea Corner", "eating_out"), ("RS Puram Medicals", "health"),
                   ("Kongu Vegetables", "groceries"), ("Trendz Salon", "personal_care")],
    "Madurai":    [("Meenakshi Provision Stores", "groceries"), ("Jigarthanda Corner", "eating_out"), ("Madurai Medicals", "health"),
                   ("Thirunagar Vegetables", "groceries"), ("Style Gents Parlour", "personal_care")],
    "Bengaluru":  [("Sri Manjunatha Provision Stores", "groceries"), ("Brahmins Coffee Bar", "eating_out"), ("Namdharis Fresh", "groceries"),
                   ("Sri Raghavendra Medicals", "health"), ("Hair Studio Unisex", "personal_care"), ("Darshini Tiffin Centre", "eating_out")],
    "Hyderabad":  [("Sri Venkateswara Kirana", "groceries"), ("Nimrah Cafe Irani Chai", "eating_out"), ("Hyderabad Medicals", "health"),
                   ("Gachibowli Fruits", "groceries"), ("Looks Gents Salon", "personal_care")],
    "Kochi":      [("Kerala Stores", "groceries"), ("Chayakkada Kakkanad", "eating_out"), ("Edappally Medicals", "health"),
                   ("Vyttila Fish Market", "groceries"), ("Mirror Unisex Salon", "personal_care")],
    "Delhi":      [("Gupta General Store", "groceries"), ("Sharma Tea Corner", "eating_out"), ("Bansal Fruits And Vegetables", "groceries"),
                   ("Delhi Medicos", "health"), ("Royal Hair Salon", "personal_care"), ("Chawla Dhaba", "eating_out")],
    "Jaipur":     [("Agrawal Kirana Store", "groceries"), ("Shri Ram Chai Wala", "eating_out"), ("Jain Sabzi Bhandar", "groceries"),
                   ("Rajasthan Medical Store", "health"), ("Style Point Salon", "personal_care"), ("Mahaveer Rabdi Bhandar", "eating_out")],
    "Lucknow":    [("Awasthi Kirana Store", "groceries"), ("Sharma Ji Ki Chai", "eating_out"), ("Gomti Medical Hall", "health"),
                   ("Aliganj Sabzi Mandi", "groceries"), ("New Look Salon", "personal_care")],
    "Patna":      [("Sinha General Store", "groceries"), ("Litti Chokha Corner", "eating_out"), ("Patna Medical Hall", "health"),
                   ("Kankarbagh Vegetables", "groceries"), ("Smart Look Salon", "personal_care")],
    "Indore":     [("Malwa Kirana Store", "groceries"), ("Sarafa Poha Jalebi", "eating_out"), ("Indore Medical Stores", "health"),
                   ("Vijay Nagar Fruits", "groceries"), ("Hairline Salon", "personal_care")],
    "Mumbai":     [("Patel Provision Stores", "groceries"), ("Mumbai Chai Centre", "eating_out"), ("Sai Fruits And Veg", "groceries"),
                   ("Shree Krishna Chemist", "health"), ("Looks Unisex Salon", "personal_care"), ("Ganesh Vada Pav", "eating_out")],
    "Pune":       [("Joshi Kirana Stores", "groceries"), ("Amruttulya Tea", "eating_out"), ("Kothrud Medicals", "health"),
                   ("Baner Fresh Vegetables", "groceries"), ("Style Studio Salon", "personal_care")],
    "Ahmedabad":  [("Shah Provision Store", "groceries"), ("Lucky Tea Stall", "eating_out"), ("Navrangpura Medical", "health"),
                   ("Satellite Fruits", "groceries"), ("Sparsh Salon", "personal_care")],
    "Kolkata":    [("Das Grocery Store", "groceries"), ("Dacres Lane Tea Stall", "eating_out"), ("Salt Lake Medical", "health"),
                   ("Gariahat Fish And Veg", "groceries"), ("Kolkata Hair Studio", "personal_care")],
}


def _slug(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in s).strip("_").replace("__", "_")


def load_merchants() -> list[dict]:
    rows = []
    for line in _MERCHANTS.strip().splitlines():
        key, disp, narr, cat, sub, vpa, cities, subflag = line.split("|")
        rows.append(dict(key=key, name=disp, narr=narr, category=cat, subcategory=sub or None,
                         vpa=vpa, cities=None if cities == "*" else cities.split(","),
                         is_subscription_likely=subflag == "1", local=False))
    for city, items in _LOCAL.items():
        for name, cat in items:
            key = "local_" + _slug(city) + "_" + _slug(name)
            digest = int(hashlib.md5(f"{city}|{name}".encode()).hexdigest(), 16)
            handle = "q" + str(digest % 10**9).zfill(9) + "@ybl"
            rows.append(dict(key=key, name=name, narr=name.upper(), category=cat, subcategory=None,
                             vpa=handle, cities=[city], is_subscription_likely=False, local=True))
    return rows


MERCHANTS = load_merchants()
MERCHANT_BY_KEY = {m["key"]: m for m in MERCHANTS}

# ---------------------------------------------------------------------------
# Names (Latin script, as they appear in Indian bank data). All combinations are invented.
# ---------------------------------------------------------------------------
NAMES = {
    "tamil": dict(
        male=["Karthik", "Arun", "Vignesh", "Prakash", "Senthil", "Murugan", "Saravanan", "Bala", "Dinesh", "Gokul",
              "Hari", "Surya", "Vijay", "Ashwin", "Naveen", "Ramesh", "Ganesh", "Selvam", "Manikandan", "Siva",
              "Venkatesh", "Mohan", "Pradeep", "Raghu", "Sathish", "Balaji", "Kumaran", "Elango"],
        female=["Lakshmi", "Divya", "Priya", "Kavya", "Sneha", "Meena", "Revathi", "Anitha", "Deepa", "Gayathri",
                "Nithya", "Swetha", "Janani", "Keerthana", "Selvi", "Bhavani", "Vidya", "Malathi", "Sangeetha", "Padma",
                "Kalaivani", "Abinaya", "Sowmya", "Pavithra"],
        surname=["Ramasamy", "Krishnan", "Subramanian", "Natarajan", "Murugesan", "Rajendran", "Srinivasan", "Narayanan",
                 "Pandian", "Venkataraman", "Chandrasekaran", "Palanisamy", "Annamalai", "Iyer", "Sundaram", "Ganesan"]),
    "south": dict(
        male=["Manjunath", "Shreyas", "Raghavendra", "Harish", "Prajwal", "Kiran", "Sandeep", "Abhishek", "Naveen", "Srikanth",
              "Ravi", "Teja", "Varun", "Arjun", "Nikhil", "Rahul", "Anil", "Pradeep", "Sachin", "Akhil"],
        female=["Kavitha", "Deepika", "Suma", "Shwetha", "Ananya", "Megha", "Riya", "Pooja", "Bhavya", "Sahana",
                "Divya", "Harini", "Lavanya", "Sravani", "Anjali", "Aishwarya", "Neha", "Keerthi"],
        surname=["Gowda", "Rao", "Shetty", "Hegde", "Bhat", "Kulkarni", "Reddy", "Naidu", "Nair", "Menon", "Pillai",
                 "Murthy", "Prasad", "Kumar", "Varma", "Shenoy"]),
    "hindi": dict(
        male=["Rahul", "Amit", "Vikas", "Sonu", "Rohit", "Ankit", "Saurabh", "Deepak", "Manish", "Ravi", "Sandeep",
              "Pankaj", "Rajesh", "Mukesh", "Suresh", "Ajay", "Vivek", "Gaurav", "Nitin", "Arjun", "Aman", "Ramesh"],
        female=["Sunita", "Pooja", "Neha", "Priyanka", "Anjali", "Kavita", "Rekha", "Shalini", "Ritu", "Sonia", "Komal",
                "Preeti", "Meenakshi", "Nisha", "Geeta", "Sapna", "Anita", "Rani", "Suman"],
        surname=["Kumar", "Sharma", "Verma", "Gupta", "Agarwal", "Singh", "Yadav", "Jain", "Mishra", "Pandey", "Chauhan",
                 "Saini", "Meena", "Choudhary", "Rathore", "Tiwari", "Srivastava", "Sinha", "Prasad"]),
    "west": dict(
        male=["Vikram", "Rohan", "Aditya", "Pratik", "Sagar", "Tejas", "Nikhil", "Siddharth", "Kunal", "Omkar", "Harsh",
              "Yash", "Chirag", "Parth", "Anand", "Mehul"],
        female=["Neha", "Shruti", "Snehal", "Pooja", "Priya", "Aarti", "Riddhi", "Tanvi", "Rutuja", "Krupa", "Dhwani",
                "Prachi", "Mansi", "Isha"],
        surname=["Mehta", "Shah", "Patil", "Joshi", "Kulkarni", "Deshmukh", "Desai", "Patel", "Iyer", "Pillai", "Nair",
                 "D'Souza", "Fernandes", "Gaikwad", "Jadhav", "Parekh"]),
    "east": dict(
        male=["Arnab", "Sourav", "Debasish", "Subhajit", "Rajib", "Abhijit", "Sandip", "Ankan", "Prosenjit", "Tanmay"],
        female=["Riya", "Moumita", "Sohini", "Payel", "Ananya", "Tanushree", "Sreemoyee", "Debjani", "Puja", "Rimpa"],
        surname=["Banerjee", "Chatterjee", "Mukherjee", "Das", "Ghosh", "Sen", "Bose", "Dutta", "Roy", "Saha"]),
}

# ---------------------------------------------------------------------------
# Calendar: festivals and sales (dates approximate; synthetic data tolerates a day's error)
# ---------------------------------------------------------------------------
# (name, start, end, regions or None for all, effects {category: multiplier})
FESTIVALS = [
    ("Guru Nanak Jayanti", date(2025, 11, 5), date(2025, 11, 5), ["hindi"], {"eating_out": 1.3}),
    ("Chhath Puja", date(2025, 10, 27), date(2025, 10, 28), ["hindi"], {}),
    ("Christmas", date(2025, 12, 23), date(2025, 12, 26), None, {"eating_out": 1.6, "shopping": 1.6, "gifts_donations": 2.5, "entertainment": 1.6}),
    ("New Year", date(2025, 12, 30), date(2026, 1, 1), None, {"eating_out": 2.0, "entertainment": 1.8, "food_delivery": 1.4}),
    ("Pongal", date(2026, 1, 13), date(2026, 1, 17), ["tamil"], {"shopping": 2.5, "groceries": 1.5, "travel": 2.0, "gifts_donations": 2.0}),
    ("Makar Sankranti", date(2026, 1, 14), date(2026, 1, 14), ["hindi", "west", "south"], {"groceries": 1.3, "shopping": 1.3}),
    ("Republic Day sale", date(2026, 1, 16), date(2026, 1, 20), None, {"shopping": 2.2}),
    ("Holi", date(2026, 3, 2), date(2026, 3, 4), ["hindi", "west"], {"groceries": 1.6, "eating_out": 1.5, "shopping": 1.4, "gifts_donations": 1.5}),
    ("Ugadi / Gudi Padwa", date(2026, 3, 19), date(2026, 3, 19), ["south", "west"], {"groceries": 1.5, "shopping": 1.6}),
    ("Eid al-Fitr", date(2026, 3, 20), date(2026, 3, 21), None, {"eating_out": 1.3}),
    ("Tamil New Year", date(2026, 4, 14), date(2026, 4, 14), ["tamil"], {"groceries": 1.4, "shopping": 1.6}),
    ("Akshaya Tritiya", date(2026, 4, 19), date(2026, 4, 20), None, {"shopping": 1.3}),
    ("Summer sale", date(2026, 5, 7), date(2026, 5, 11), None, {"shopping": 1.8}),
    ("Prime Day", date(2026, 7, 11), date(2026, 7, 12), None, {"shopping": 2.0}),
    ("Independence Day sale", date(2026, 8, 6), date(2026, 8, 10), None, {"shopping": 1.8}),
    ("Onam", date(2026, 8, 25), date(2026, 8, 27), ["south"], {"groceries": 1.6, "shopping": 1.8}),
    ("Raksha Bandhan", date(2026, 8, 27), date(2026, 8, 28), ["hindi", "west"], {"gifts_donations": 3.0, "shopping": 1.5, "eating_out": 1.3}),
    ("Ganesh Chaturthi", date(2026, 9, 13), date(2026, 9, 15), ["west", "south", "tamil"], {"groceries": 1.5, "shopping": 1.4}),
    ("Festive sale (Big Billion Days / Great Indian Festival)", date(2026, 9, 23), date(2026, 10, 3), None, {"shopping": 2.8}),
    ("Navratri", date(2026, 10, 11), date(2026, 10, 19), ["hindi", "west", "east"], {"shopping": 1.6, "eating_out": 1.3}),
    ("Ayudha Pooja / Dussehra", date(2026, 10, 19), date(2026, 10, 20), None, {"shopping": 1.6, "groceries": 1.4, "gifts_donations": 1.5}),
    ("Karwa Chauth", date(2026, 10, 29), date(2026, 10, 29), ["hindi"], {"shopping": 1.4}),
    ("Dhanteras / Diwali / Bhai Dooj", date(2026, 11, 5), date(2026, 11, 11), None,
     {"shopping": 3.0, "gifts_donations": 3.5, "groceries": 1.7, "eating_out": 1.5, "travel": 1.8, "family_support": 1.0}),
    ("Chhath Puja", date(2026, 11, 14), date(2026, 11, 16), ["hindi"], {"travel": 1.5}),
]

# Bank holidays used for business-day logic (approximate, national/major).
BANK_HOLIDAYS = {
    date(2025, 11, 5), date(2025, 12, 25), date(2026, 1, 26), date(2026, 3, 4), date(2026, 3, 21),
    date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 8, 15), date(2026, 10, 2),
    date(2026, 10, 20), date(2026, 11, 9),
}

# ---------------------------------------------------------------------------
# Real AMFI schemes (codes and latest NAVs verified via mfapi.in on 20 Nov 2026)
# ---------------------------------------------------------------------------
# code, name, category, latest NAV, NAV date, annual drift, annual vol, beta to market
FUNDS = [
    (120716, "UTI Nifty 50 Index Fund - Direct Plan - Growth", "index", 179.7634, date(2026, 11, 19), 0.10, 0.13, 1.00),
    (122639, "Parag Parikh Flexi Cap Fund - Direct Plan - Growth", "flexi_cap", 94.1452, date(2026, 11, 18), 0.14, 0.12, 0.75),
    (118955, "HDFC Flexi Cap Fund - Direct Plan - Growth Option", "flexi_cap", 2366.2160, date(2026, 11, 18), 0.13, 0.14, 0.95),
    (119598, "SBI Large Cap Fund - Direct Plan - Growth", "large_cap", 108.5170, date(2026, 11, 19), 0.11, 0.13, 0.95),
    (120465, "Axis Large Cap Fund - Direct Plan - Growth Option", "large_cap", 74.3200, date(2026, 11, 17), 0.09, 0.13, 0.95),
    (118825, "Mirae Asset Large Cap Fund - Direct Plan - Growth", "large_cap", 133.2150, date(2026, 11, 18), 0.10, 0.13, 0.97),
    (120586, "ICICI Prudential Large Cap Fund (erstwhile Bluechip Fund) - Direct Plan - Growth", "large_cap", 123.4800, date(2026, 11, 18), 0.12, 0.13, 0.95),
    (118989, "HDFC Mid Cap Fund - Direct Plan - Growth Option", "mid_cap", 228.6310, date(2026, 11, 18), 0.16, 0.17, 1.10),
    (127042, "Motilal Oswal Midcap Fund", "mid_cap", 120.4270, date(2026, 11, 19), 0.15, 0.20, 1.15),
    (118778, "Nippon India Small Cap Fund - Direct Plan - Growth Option", "small_cap", 201.5371, date(2026, 11, 18), 0.15, 0.21, 1.20),
    (125497, "SBI SMALL CAP FUND - Direct Plan - Growth", "small_cap", 208.9322, date(2026, 11, 18), 0.13, 0.19, 1.10),
    (125354, "Axis Small Cap Fund - Direct Plan - Growth Option", "small_cap", 134.5200, date(2026, 11, 17), 0.13, 0.19, 1.10),
    (120503, "Axis ELSS- Tax Saver Fund - Direct Plan - Growth Option", "elss", 115.6089, date(2026, 11, 18), 0.10, 0.14, 0.95),
    (135781, "Mirae Asset ELSS Tax Saver Fund - Direct Plan - Growth", "elss", 58.2430, date(2026, 11, 18), 0.12, 0.14, 1.00),
    (119091, "HDFC Liquid Fund - Direct Plan - Growth Option", "liquid", 5640.9618, date(2026, 11, 19), 0.064, 0.003, 0.0),
    (119788, "SBI GOLD FUND - Direct Plan - Growth", "gold", 39.2203, date(2026, 11, 19), 0.18, 0.15, 0.0),
]
FUND_BY_CODE = {f[0]: f for f in FUNDS}
