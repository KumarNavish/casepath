"""Built-in neutral lists for story seeds. No real persons: first names and surnames are common ones combined at
random, so no combination is meant to denote anyone. Organisation names are composed from neutral landscape words
and a generic suffix; they are not taken from any register and are not meant to name a real company (check a
final set against a commercial register before publication). Places are Swiss municipalities with their canton;
streets are generic street names."""

FIRST_DE = ["Andrea", "Beat", "Claudia", "Daniel", "Esther", "Fabian", "Gabriela", "Heinz", "Irene", "Jonas",
            "Karin", "Lukas", "Monika", "Nicole", "Oliver", "Petra", "Reto", "Sabine", "Thomas", "Ursula",
            "Verena", "Walter", "Yvonne", "Simon", "Martina", "Stefan", "Corinne", "Marco", "Lea", "Adrian",
            "Nadine", "Patrick", "Rahel", "Samuel", "Tamara", "Urs", "Livia", "Dominik", "Seraina", "Matthias"]
FIRST_EN = ["Alice", "Ben", "Clara", "David", "Emma", "Felix", "Grace", "Henry", "Isla", "Jack", "Kate", "Liam",
            "Maya", "Noah", "Olivia", "Paul", "Rachel", "Sam", "Tara", "Victor", "Laura", "Mark", "Nina", "Owen",
            "Ruth", "Sophie", "Tom", "Anna", "Chris", "Eva", "Hannah", "Ian", "Julia", "Leo", "Megan", "Peter"]
SURNAMES = ["Ammann", "Baumann", "Bieri", "Brunner", "Bucher", "Egli", "Fankhauser", "Frei", "Gerber", "Graf",
            "Hofer", "Huber", "Imhof", "Kaufmann", "Keller", "Kuhn", "Lehmann", "Lüthi", "Marti", "Meier",
            "Moser", "Müller", "Näf", "Odermatt", "Rüegg", "Schmid", "Schneider", "Steiner", "Suter", "Tanner",
            "Vogel", "Wälti", "Weber", "Widmer", "Wyss", "Zaugg", "Zimmermann", "Bachmann", "Gisler", "Hürlimann",
            "Carter", "Ellis", "Foster", "Hughes", "Morgan", "Palmer", "Reid", "Shaw", "Turner", "Walsh"]
ORG_WORDS = ["Seematt", "Talgrund", "Birkenrain", "Sonnbühl", "Lindenmatt", "Erlenhof", "Weidgrund", "Rebhalde",
             "Kirschbaum", "Moosacker", "Steinbruch", "Bachtel", "Feldegg", "Hagenbuch", "Rosenau", "Ahornweid"]
ORG_SUFFIX_DE = ["Verwaltungs GmbH", "Immobilien AG", "Betriebs AG", "Dienste GmbH", "Genossenschaft", "Handels AG"]
ORG_SUFFIX_EN = ["Management Ltd", "Property Ltd", "Services Ltd", "Holdings Ltd", "Cooperative", "Trading Ltd"]
PLACES = [("Aarau", "AG"), ("Baden", "AG"), ("Wohlen", "AG"), ("Bern", "BE"), ("Thun", "BE"), ("Biel/Bienne", "BE"),
          ("Burgdorf", "BE"), ("Langenthal", "BE"), ("Basel", "BS"), ("Liestal", "BL"), ("Allschwil", "BL"),
          ("Fribourg", "FR"), ("Luzern", "LU"), ("Emmen", "LU"), ("Kriens", "LU"), ("St. Gallen", "SG"),
          ("Wil", "SG"), ("Rapperswil-Jona", "SG"), ("Schaffhausen", "SH"), ("Solothurn", "SO"), ("Olten", "SO"),
          ("Frauenfeld", "TG"), ("Kreuzlingen", "TG"), ("Zug", "ZG"), ("Baar", "ZG"), ("Winterthur", "ZH"),
          ("Uster", "ZH"), ("Dübendorf", "ZH"), ("Wädenswil", "ZH"), ("Zürich", "ZH"), ("Chur", "GR"),
          ("Herisau", "AR"), ("Schwyz", "SZ"), ("Altdorf", "UR"), ("Sarnen", "OW"), ("Stans", "NW"),
          ("Glarus", "GL"), ("Lausanne", "VD"), ("Yverdon-les-Bains", "VD"), ("Neuchâtel", "NE")]
STREETS = ["Bahnhofstrasse", "Lindenweg", "Gartenstrasse", "Kirchgasse", "Schulhausstrasse", "Birkenweg",
           "Feldstrasse", "Mattenweg", "Rosenweg", "Dorfstrasse", "Hauptstrasse", "Seestrasse", "Bergstrasse",
           "Sonnenweg", "Wiesenstrasse", "Ahornweg", "Brunnenrain", "Mühleweg", "Talstrasse", "Hofackerstrasse"]
