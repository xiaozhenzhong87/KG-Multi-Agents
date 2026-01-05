from neo4j import GraphDatabase

uri = "bolt://localhost:7688"
auth = ("neo4j", "12345678")

driver = GraphDatabase.driver(uri, auth=auth)

with driver.session() as session:
    nodes = session.run(
        "MATCH (n:Entity {namespace:'umls_kg'}) RETURN count(n) AS c"
    ).single()["c"]

    rels = session.run(
        "MATCH ()-[r]->() WHERE r.namespace='umls_kg' RETURN count(r) AS c"
    ).single()["c"]

    top = session.run(
        "MATCH ()-[r]->() WHERE r.namespace='umls_kg' "
        "RETURN type(r) AS relType, count(r) AS cnt "
        "ORDER BY cnt DESC LIMIT 20"
    ).values()

print({'nodes': nodes, 'relationships': rels, 'top20': top})
driver.close()