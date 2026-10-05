import pandas as pd
import json
import sys
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS, XSD

EX = Namespace("http://example.org/mkr/")

def clean_file(csv_file):
    df = pd.read_csv(csv_file)

    for column in df.select_dtypes(include=['object']).columns:
        df[column] = df[column].str.strip()

    df["flight_id"] = df["flight_id"].str.upper()
    selected_columns = ["from_city", "to_city", "from_country", "to_country", "airline"]
    for column in selected_columns:
        df[column] = df[column].str.title()

    df["dep_date"] = pd.to_datetime(df["dep_date"], format="mixed", dayfirst=True, errors="coerce")
    df["dep_date"] = df["dep_date"].dt.strftime("%Y-%m-%d")
    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce")
    df["price_eur"] = pd.to_numeric(df["price_eur"], errors="coerce")
    df["note"] = df["note"].replace("", pd.NA)
    df = df.drop_duplicates(subset=["flight_id"], keep="first")
    df["price_eur"] = df["price_eur"].round(2)

    return df

def replace_uri(uri):
    return str(uri).replace(" ", "_")

def load_params(filename):
    with open(filename, "r") as f:
        return json.load(f)

def build_graph(data):
    params = load_params("params.json")
    graph = Graph()
    graph.bind("ex", EX)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)

    graph.add((EX.Flight, RDF.type, RDFS.Class))
    graph.add((EX.Airline, RDF.type, RDFS.Class))
    graph.add((EX.City, RDF.type, RDFS.Class))
    graph.add((EX.Country, RDF.type, RDFS.Class))
    graph.add((EX.BudgetFlight, RDF.type, RDFS.Class))
    graph.add((EX.LongFlight, RDF.type, RDFS.Class))
    graph.add((EX.BudgetFlight, RDFS.subClassOf, EX.Flight))
    graph.add((EX.LongFlight, RDFS.subClassOf, EX.Flight))

    graph.add((EX.operatedBy, RDF.type, RDF.Property))
    graph.add((EX.operatedBy, RDFS.domain, EX.Flight))
    graph.add((EX.operatedBy, RDFS.range, EX.Airline))

    graph.add((EX.departsFrom, RDF.type, RDF.Property))
    graph.add((EX.departsFrom, RDFS.domain, EX.Flight))
    graph.add((EX.departsFrom, RDFS.range, EX.City))

    graph.add((EX.arrivesAt, RDF.type, RDF.Property))
    graph.add((EX.arrivesAt, RDFS.domain, EX.Flight))
    graph.add((EX.arrivesAt, RDFS.range, EX.City))

    graph.add((EX.locatedIn, RDF.type, RDF.Property))
    graph.add((EX.locatedIn, RDFS.domain, EX.City))
    graph.add((EX.locatedIn, RDFS.range, EX.Country))

    graph.add((EX.departureDate, RDF.type, RDF.Property))
    graph.add((EX.departureDate, RDFS.domain, EX.Flight))
    graph.add((EX.departureDate, RDFS.range, XSD.date))

    graph.add((EX.durationMin, RDF.type, RDF.Property))
    graph.add((EX.durationMin, RDFS.domain, EX.Flight))
    graph.add((EX.durationMin, RDFS.range, XSD.integer))

    graph.add((EX.priceEur, RDF.type, RDF.Property))
    graph.add((EX.priceEur, RDFS.domain, EX.Flight))
    graph.add((EX.priceEur, RDFS.range, XSD.decimal))

    busy_countries = data["from_country"].value_counts()
    busy_countries = busy_countries[busy_countries >= 2].index
    for _, flight in data.iterrows():
        flight_uri = EX[f"flight/{flight["flight_id"]}"]
        airline_uri = EX[f"airline/{replace_uri(flight['airline'])}"]
        from_city_uri = EX[f"city/{replace_uri(flight['from_city'])}"]
        to_city_uri = EX[f"city/{replace_uri(flight['to_city'])}"]
        from_country_uri = EX[f"country/{replace_uri(flight['from_country'])}"]
        to_country_uri = EX[f"country/{replace_uri(flight['to_country'])}"]

        if pd.notna(flight["price_eur"]) and flight["price_eur"] <= params["budget_threshold_eur"]:
            graph.add((flight_uri, RDF.type, EX.BudgetFlight))
        elif pd.notna(flight["duration_min"]) and flight["duration_min"] >= params["long_flight_min"]:
            graph.add((flight_uri, RDF.type, EX.LongFlight))
        else:
            graph.add((flight_uri, RDF.type, EX.Flight))

        # graph.add((flight_uri, RDF.type, EX.Flight))
        graph.add((airline_uri, RDF.type, EX.Airline))
        graph.add((from_city_uri, RDF.type, EX.City))
        graph.add((to_city_uri, RDF.type, EX.City))
        graph.add((from_country_uri, RDF.type, EX.Country))
        graph.add((to_country_uri, RDF.type, EX.Country))

        graph.add((airline_uri, RDFS.label, Literal(flight['airline'], lang="en")))
        graph.add((from_city_uri, RDFS.label, Literal(flight['from_city'], lang="en")))
        graph.add((to_city_uri, RDFS.label, Literal(flight['to_city'], lang="en")))
        graph.add((from_country_uri, RDFS.label, Literal(flight['from_country'], lang="en")))
        graph.add((to_country_uri, RDFS.label, Literal(flight['to_country'], lang="en")))

        graph.add((flight_uri, EX.operatedBy, airline_uri))
        graph.add((flight_uri, EX.departsFrom, from_city_uri))
        graph.add((flight_uri, EX.arrivesAt, to_city_uri))
        graph.add((from_city_uri, EX.locatedIn, from_country_uri))
        graph.add((to_city_uri, EX.locatedIn, to_country_uri))

        if pd.notna(flight["dep_date"]):
            graph.add((flight_uri, EX.departureDate, Literal(flight['dep_date'], datatype=XSD.date)))
        if pd.notna(flight["duration_min"]):
            graph.add((flight_uri, EX.durationMin, Literal(flight['duration_min'], datatype=XSD.integer)))
        if pd.notna(flight["price_eur"]):
            graph.add((flight_uri, EX.priceEur, Literal(flight['price_eur'], datatype=XSD.decimal)))

        if pd.notna(flight["note"]):
            note = flight["note"]
            if note.startswith("delay="):
                delay_part, source_part = note.split(";by=")
                delay = int(delay_part.replace("delay=", ""))
                source = source_part
                statement_uri = EX[f"stmt/{flight["flight_id"]}-delay"]
                source_uri = EX[f"source/{replace_uri(source)}"]
                graph.add((statement_uri, RDF.type, RDF.Statement))
                graph.add((statement_uri, RDF.subject, flight_uri))
                graph.add((statement_uri, RDF.predicate, EX.hasDelayMinutes))
                graph.add((statement_uri, RDF.object, Literal(delay, datatype=XSD.integer)))
                graph.add((statement_uri, EX.reportedBy, source_uri))

        if flight["from_country"] in busy_countries:
            graph.add((flight_uri, EX.fromBusyCountry, Literal(True, datatype=XSD.boolean)))

    return graph


if __name__ == '__main__':
    csv_file = sys.argv[1]
    params_file = sys.argv[2]
    output_file = sys.argv[3]
    data = clean_file(csv_file)
    params = load_params(params_file)
    graph = build_graph(data, params)

    graph.serialize(destination=output_file, format="turtle")